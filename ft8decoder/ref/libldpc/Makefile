CC=gcc
CFLAGS=-O3 -fPIC
LDFLAGS=-shared

all: libldpc.so

libldpc.so: libldpc.c arrays.h
	$(CC) $(CFLAGS) libldpc.c $(LDFLAGS) -o libldpc.so

clean:
	rm -f libldpc.so
