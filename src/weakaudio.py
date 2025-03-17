#
# get at sound cards using pyaudio / portaudio.
# 

import sys
import numpy
import time
import threading
import multiprocessing
import os

import weakutil

# desc is [ "6", "0" ] for a sound card -- sixth card, channel 0 (left).
def new(desc, rate):
    # sound card?
    if desc[0].isdigit():
        return Stream(int(desc[0]), int(desc[1]), rate)

    sys.stderr.write("weakaudio: cannot understand card %s\n" % (desc[0]))
    usage()
    sys.exit(1)

# need a single one of these even if multiple streams.
global_pya = None

def pya():
    global global_pya
    import pyaudio
    if global_pya == None:
        # suppress Jack and ALSA error messages on Linux.
        #nullfd = os.open("/dev/null", 1)
        #oerr = os.dup(2)
        #os.dup2(nullfd, 2)

        global_pya = pyaudio.PyAudio()

        #os.dup2(oerr, 2)
        #os.close(oerr)
        #os.close(nullfd)
    return global_pya

# find the lowest supported input rate >= rate.
# needed on Linux but not the Mac (which converts as needed).
def x_pya_input_rate(card, rate):
    import pyaudio
    rates = [ rate, 8000, 11025, 12000, 16000, 22050, 44100, 48000 ]
    for r in rates:
        if r >= rate:
            ok = False
            try:
                ok = pya().is_format_supported(r,
                                               input_device=card,
                                               input_format=pyaudio.paInt16,
                                               input_channels=1)
            except:
                pass
            if ok:
                return r
    sys.stderr.write("weakaudio: no input rate >= %d\n" % (rate))
    sys.exit(1)

# sub-process to avoid initializing pyaudio in main
# process, since that makes subsequent forks and
# multiprocessing not work.
def pya_input_rate(card, rate):
    rpipe, wpipe = multiprocessing.Pipe(False)
    pid = os.fork()
    if pid == 0:
        rpipe.close()
        x = x_pya_input_rate(card, rate)
        wpipe.send(x)
        os._exit(0)
    wpipe.close()
    x = rpipe.recv()
    os.waitpid(pid, 0)
    rpipe.close()
    return x

def x_pya_output_rate(card, rate):
    import pyaudio
    rates = [ rate, 8000, 11025, 12000, 16000, 22050, 44100, 48000 ]
    for r in rates:
        if r >= rate:
            ok = False
            try:
                ok = pya().is_format_supported(r,
                                               output_device=card,
                                               output_format=pyaudio.paInt16,
                                               output_channels=1)
            except:
                pass
            if ok:
                return r
    sys.stderr.write("weakaudio: no output rate >= %d\n" % (rate))
    sys.exit(1)

def pya_output_rate(card, rate):
    rpipe, wpipe = multiprocessing.Pipe(False)
    pid = os.fork()
    if pid == 0:
        rpipe.close()
        x = x_pya_output_rate(card, rate)
        wpipe.send(x)
        os._exit(0)
    wpipe.close()
    x = rpipe.recv()
    os.waitpid(pid, 0)
    rpipe.close()
    return x

class Stream:
    def __init__(self, card, chan, rate):
        self.use_oss = False
        #self.use_oss = ("freebsd" in sys.platform)
        self.card = card
        self.chan = chan

        # UNIX time of audio stream time zero.
        self.t0 = None

        if rate == None:
            rate = pya_input_rate(card, 8000)

        self.rate = rate # the sample rate the app wants.
        self.cardrate = rate # the rate at which the card is running.

        self.cardbufs = [ ]
        self.cardlock = threading.Lock()

        self.last_adc_end = None
        self.last_end_time = None

        if self.use_oss:
            self.oss_open()
        else:
            self.pya_open()

        self.resampler = weakutil.Resampler(self.cardrate, self.rate)

        # rate at which len(self.raw_read()) increases.
        self.rawrate = self.cardrate

    # returns [ buf, tm ]
    # where tm is UNIX seconds of the last sample.
    # non-blocking.
    # reads from a pipe from pya_dev2pipe in the pya sub-process.
    # XXX won't work for oss.
    def read(self):
        [ buf1, tm ] = self.raw_read()
        buf2 = self.postprocess(buf1)
        return [ buf2, tm ]

    def raw_read(self):
        bufs = [ ]
        end_time = self.last_end_time
        while self.rpipe.poll():
            e = self.rpipe.recv()
            # e is [ pcm, unix_end_time ]
            bufs.append(e[0])
            end_time = e[1]

        if len(bufs) > 0:
            buf = numpy.concatenate(bufs)
        else:
            buf = numpy.array([])

        self.last_end_time = end_time

        return [ buf, end_time ]

    def postprocess(self, buf):
        if len(buf) > 0:
            buf = self.resampler.resample(buf)
        return buf

    def junklog(self, msg):
      msg1 = "[%d, %d] %s\n" % (self.card, self.chan, msg)
      sys.stderr.write(msg1)
      f = open("ft8-junk.txt", "a")
      f.write(msg1)
      f.close()

    # PyAudio calls this in a separate thread.
    def pya_callback(self, in_data, frame_count, time_info, status):
        import pyaudio
      
        if status != 0:
            self.junklog("pya_callback status %d\n" % (status))

        pcm = numpy.fromstring(in_data, dtype=numpy.int16)
        pcm = pcm[self.chan::self.chans]

        assert frame_count == len(pcm)

        # time of first sample in pcm[], in seconds since start.
        adc_time = time_info['input_buffer_adc_time']
        # time of last sample
        adc_end = adc_time + (len(pcm) / float(self.cardrate))

        if self.last_adc_end != None:
            if adc_end < self.last_adc_end or adc_end > self.last_adc_end + 5:
                self.junklog("pya last_adc_end %s adc_end %s" % (self.last_adc_end, adc_end))
            expected = (adc_end - self.last_adc_end) * float(self.cardrate)
            expected = int(round(expected))
            shortfall = expected - len(pcm)
            if abs(shortfall) > 20:
                self.junklog("pya expected %d got %d" % (expected, len(pcm)))
                #if shortfall > 100:
                #    pcm = numpy.append(numpy.zeros(shortfall, dtype=pcm.dtype), pcm)
                    
        self.last_adc_end = adc_end

        # set up to convert from stream time to UNIX time.
        # pya_strm.get_time() returns the UNIX time corresponding
        # to the current audio stream time. it's PortAudio's Pa_GetStreamTime().
        if self.t0 == None:
            if self.pya_strm == None:
                return ( None, pyaudio.paContinue )
            ut = time.time()
            st = self.pya_strm.get_time()
            self.t0 = ut - st

        # translate time of last sample to UNIX time.
        unix_end = adc_end + self.t0

        self.cardlock.acquire()
        self.cardbufs.append([ pcm, unix_end ])
        self.cardlock.release()

        return ( None, pyaudio.paContinue )

    def pya_open(self):
        self.cardrate = pya_input_rate(self.card, self.rate)
        
        # read from sound card in a separate process, since Python
        # scheduler seems sometimes not to run the py audio thread
        # often enough.
        sys.stdout.flush()
        rpipe, wpipe = multiprocessing.Pipe(False)
        proc = multiprocessing.Process(target=self.pya_dev2pipe, args=[rpipe,wpipe])
        proc.start()
        wpipe.close()
        self.rpipe = rpipe

    # executes in a sub-process.
    def pya_dev2pipe(self, rpipe, wpipe):
        import pyaudio

        rpipe.close()

        if "freebsd" in sys.platform:
          # always ask for 2 channels, since on FreeBSD if you
          # open left with chans=1 and right with chans=2 you
          # get mixing.
          self.chans = 2
        else:
          # but needs to be 1 for RigBlaster on Linux.
          self.chans = 1
        assert self.chan < self.chans

        # perhaps this controls how often the callback is called.
        # too big and ft8.py's read() is delayed long enough to
        # cut into FT8 decoding time. too small and apparently the
        # callback thread can't keep up.
        bufsize = int(self.cardrate / 8) # was 4

        # pya.open in this sub-process so that pya starts the callback thread
        # here too.
        xpya = pya()
        self.pya_strm = None
        self.pya_strm = xpya.open(format=pyaudio.paInt16,
                                   input_device_index=self.card,
                                   channels=self.chans,
                                   rate=self.cardrate,
                                   frames_per_buffer=bufsize,
                                   stream_callback=self.pya_callback,
                                   output=False,
                                   input=True)

        # copy buffers from self.cardbufs, where pya_callback left them,
        # to the pipe to the parent process. can't do this in the callback
        # because the pipe write might block.
        # each object on the pipe is [ pcm, unix_end ].
        while True:
            self.cardlock.acquire()
            bufs = self.cardbufs
            self.cardbufs = [ ]
            self.cardlock.release()
            if len(bufs) > 0:
                for e in bufs:
                    try:
                        wpipe.send(e)
                    except:
                        os._exit(1)
            else:
                time.sleep(0.05)
            

    def oss_open(self):
        import ossaudiodev
        self.oss = ossaudiodev.open("/dev/dsp" + str(self.card) + ".0", "r")
        self.oss.setfmt(ossaudiodev.AFMT_S16_LE)
        self.oss.channels(2)
        assert self.oss.speed(self.rate) == self.rate
        self.th = threading.Thread(target=lambda : self.oss_thread())
        self.th.daemon = True
        self.th.start()

    # dedicating reading thread because oss's buffering seems
    # to be pretty limited, and wspr.py spends 50 seconds in
    # process() while not calling read().
    def oss_thread(self):
        # XXX the card probably doesn't read the first sample at this
        # exact point, and probably doesn't read at exactly self.rate
        # samples per second.
        self.cardtime = time.time()

        while True:
            # the read() blocks.
            buf = self.oss.read(8192)
            assert len(buf) > 0
            both = numpy.fromstring(buf, dtype=numpy.int16)
            got = both[self.chan::self.chans]

            self.cardlock.acquire()
            self.cardbufs.append(got)
            self.cardtime += len(got) / float(self.rate)
            self.cardlock.release()

    # print levels, to help me adjust volume control.
    def levels(self):
        while True:
            time.sleep(1)
            [ buf, junk ] = self.read()
            if len(buf) > 0:
                print("avg=%.0f max=%.0f" % (numpy.mean(abs(buf)), numpy.max(buf)))

def usage():
    sys.stderr.write("card format:\n")
    sys.stderr.write("  N,C    sound card N, channel C\n")

def levels(card):
    s = new(card.split(","), 8000)
    while True:
        x = s.levels()
        sys.stdout.write("%.1f %.1f\n" % (x[0], x[1]))
        sys.stdout.flush()
        time.sleep(0.1)
