#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频录制模块

提供实时音频录制和处理功能
"""

import os
import time
import datetime
import wave
import logging
import threading
import queue
import tempfile
import pyaudio
import numpy as np
from typing import Dict, Any, Optional, List, Tuple

# 配置日志
logger = logging.getLogger('AudioRecorder')

class AudioRecorder:
    """音频录制类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """初始化音频录制器
        
        Args:
            config: 配置字典
        """
        # 默认配置
        self.config = {
            "chunk_size": 512,  # 每次读取的音频帧数
            "audio_format": pyaudio.paInt16,  # 音频格式
            "channels": 1,  # 单声道
            "sample_rate": 44100,  # 采样率
            "record_seconds": 13.5,  # 录制时长
            "advance_seconds": 0.2,  # 提前开始录制的时间
            "temp_dir": tempfile.gettempdir(),  # 临时文件目录
            "output_dir": "recordings",  # 录音输出目录
        }
        
        # 更新配置
        if config:
            self.config.update(config)
            
        # 创建输出目录
        os.makedirs(self.config["output_dir"], exist_ok=True)
        
        # 初始化PyAudio
        try:
            self.pyaudio = pyaudio.PyAudio()
            self.devices = self._get_audio_devices()
            self.active_device = None
            self.stream = None
            
            # 线程和事件控制
            self.recording = False
            self.stop_event = threading.Event()
            self.record_thread = None
            self.buffer_queue = queue.Queue(maxsize=8)  # 音频缓冲队列
            
            logger.info("音频录制器初始化完成")
        except Exception as e:
            logger.error(f"初始化PyAudio失败: {e}")
            raise
        
    def __del__(self):
        """析构函数，确保资源释放"""
        self.stop()
        if self.pyaudio:
            self.pyaudio.terminate()
            
    def _get_audio_devices(self) -> List[Dict[str, Any]]:
        """获取可用的音频设备
        
        Returns:
            设备列表
        """
        devices = []
        logger.debug(f"开始扫描音频设备，总数: {self.pyaudio.get_device_count()}")
        
        # 首先获取ALSA设备列表
        try:
            import subprocess
            # 使用arecord -l获取输入设备列表
            result = subprocess.run(["arecord", "-l"], capture_output=True, text=True)
            if result.returncode == 0:
                output = result.stdout
                # 查找所有声卡设备
                import re
                # 修改正则表达式以匹配arecord -l的输出格式
                card_devices = re.findall(r'card\s+(\d+):\s+(\w+)\s+\[([^\]]+)\],\s+device\s+(\d+):\s+(\w+)\s+\[([^\]]+)\]', output)
                
                # 添加ALSA设备
                for card_id, card_name, card_desc, device_id, device_name, device_desc in card_devices:
                    device_name = f"{card_desc} (hw:{card_id},{device_id})"
                    devices.append({
                        "index": len(devices),  # 使用当前列表长度作为索引
                        "name": device_name,
                        "channels": 1,  # 默认单声道
                        "default_sample_rate": 44100,
                        "supported_rates": [44100, 48000],
                        "is_alsa": True,
                        "card_id": int(card_id),
                        "device_id": int(device_id)
                    })
                    logger.debug(f"添加ALSA设备: {device_name}")
                    
                # 如果没有找到设备，尝试使用更宽松的匹配模式
                if not devices:
                    logger.warning("使用更宽松的匹配模式查找设备")
                    card_devices = re.findall(r'card\s+(\d+):\s+([^\n]+)', output)
                    for card_id, card_desc in card_devices:
                        if "USB" in card_desc:
                            device_name = f"{card_desc} (hw:{card_id},0)"
                            devices.append({
                                "index": len(devices),
                                "name": device_name,
                                "channels": 1,
                                "default_sample_rate": 44100,
                                "supported_rates": [44100, 48000],
                                "is_alsa": True,
                                "card_id": int(card_id),
                                "device_id": 0
                            })
                            logger.debug(f"添加USB设备: {device_name}")
        except Exception as e:
            logger.error(f"获取ALSA设备列表失败: {e}")
        
        # 然后获取PyAudio设备
        for i in range(self.pyaudio.get_device_count()):
            try:
                device_info = self.pyaudio.get_device_info_by_index(i)
                logger.debug(f"检查PyAudio设备 {i}: {device_info}")
                
                # 检查设备是否可用
                try:
                    test_stream = self.pyaudio.open(
                        format=self.config["audio_format"],
                        channels=1,
                        rate=int(device_info["defaultSampleRate"]),
                        input=True,
                        input_device_index=i,
                        frames_per_buffer=self.config["chunk_size"]
                    )
                    test_stream.close()
                except Exception as e:
                    logger.debug(f"设备 {i} 不可用: {e}")
                    continue
                
                # 检查是否为输入设备
                if device_info["maxInputChannels"] > 0:
                    # 检查设备支持的采样率
                    try:
                        supported_rates = []
                        for rate in [8000, 11025, 16000, 22050, 44100, 48000, 96000]:
                            try:
                                if self.pyaudio.is_format_supported(
                                    rate,
                                    input_device=i,
                                    input_channels=1,
                                    input_format=self.config["audio_format"]
                                ):
                                    supported_rates.append(rate)
                            except:
                                pass
                        
                        # 如果没有检测到支持的采样率，使用默认采样率
                        if not supported_rates:
                            supported_rates = [int(device_info["defaultSampleRate"])]
                            logger.warning(f"设备 {i} ({device_info['name']}) 没有检测到支持的采样率，使用默认值: {supported_rates}")
                        
                    except Exception as e:
                        logger.warning(f"设备 {i} 检测支持的采样率失败: {e}")
                        supported_rates = [44100, 48000]  # 默认假设支持这些常用采样率
                    
                    # 添加设备
                    devices.append({
                        "index": len(devices),  # 使用当前列表长度作为索引
                        "name": device_info["name"],
                        "channels": int(device_info["maxInputChannels"]),
                        "default_sample_rate": int(device_info["defaultSampleRate"]),
                        "supported_rates": supported_rates,
                        "is_alsa": False,
                        "pyaudio_index": i
                    })
                    logger.debug(f"找到PyAudio输入设备 {i}: {device_info['name']}, 通道数: {device_info['maxInputChannels']}, 支持的采样率: {supported_rates}")
                else:
                    logger.debug(f"设备 {i} ({device_info['name']}) 不是输入设备，跳过")
            except Exception as e:
                logger.error(f"获取设备 {i} 信息时出错: {e}")
        
        logger.info(f"找到 {len(devices)} 个音频输入设备")
        return devices
        
    def list_devices(self) -> List[Dict[str, Any]]:
        """列出可用的音频设备
        
        Returns:
            设备列表
        """
        return self.devices
        
    def open_device(self, device_index: int) -> bool:
        """打开音频设备
        
        Args:
            device_index: 设备索引
            
        Returns:
            是否成功
        """
        # 先关闭当前设备
        self.close_device()
        
        # 检查设备索引是否有效
        if device_index < 0 or device_index >= len(self.devices):
            device_indices = [d["index"] for d in self.devices]
            if device_index not in device_indices:
                logger.error(f"无效的设备索引: {device_index}，可用设备索引: {device_indices}")
                return False
                
        # 获取设备信息
        device = next((d for d in self.devices if d["index"] == device_index), None)
        if not device:
            logger.error(f"找不到索引为 {device_index} 的设备")
            return False
            
        # 检查是否支持配置的采样率
        sample_rate = self.config["sample_rate"]
        if sample_rate not in device["supported_rates"]:
            # 尝试使用设备的默认采样率
            sample_rate = device["default_sample_rate"]
            if sample_rate not in device["supported_rates"]:
                # 使用设备支持的第一个采样率
                sample_rate = device["supported_rates"][0]
            logger.warning(f"设备不支持配置的采样率 {self.config['sample_rate']}Hz，使用 {sample_rate}Hz")
            self.config["sample_rate"] = sample_rate
            
        logger.info(f"打开音频设备: {device['index']} ({device['name']}), 采样率: {sample_rate}Hz")
            
        try:
            if device.get("is_alsa", False):
                # 使用ALSA设备
                try:
                    import subprocess
                    # 使用arecord命令测试设备
                    test_cmd = [
                        "arecord",
                        "-D", f"hw:{device['card_id']},{device['device_id']}",
                        "-f", "S16_LE",
                        "-r", str(sample_rate),
                        "-c", "1",
                        "-t", "raw",
                        "-d", "1",
                        "/dev/null"
                    ]
                    result = subprocess.run(test_cmd, capture_output=True)
                    if result.returncode != 0:
                        logger.error(f"ALSA设备验证失败: {result.stderr.decode()}")
                        return False
                except Exception as e:
                    logger.error(f"ALSA设备验证失败: {e}")
                    return False
            else:
                # 使用PyAudio设备
                try:
                    test_stream = self.pyaudio.open(
                        format=self.config["audio_format"],
                        channels=self.config["channels"],
                        rate=sample_rate,
                        input=True,
                        input_device_index=device["pyaudio_index"],
                        frames_per_buffer=self.config["chunk_size"]
                    )
                    test_stream.close()
                except Exception as e:
                    logger.error(f"PyAudio设备验证失败: {e}")
                    return False
                
            # 打开音频流
            if device.get("is_alsa", False):
                # 使用ALSA设备
                import subprocess
                self.stream = subprocess.Popen(
                    [
                        "arecord",
                        "-D", f"hw:{device['card_id']},{device['device_id']}",
                        "-f", "S16_LE",
                        "-r", str(sample_rate),
                        "-c", "1",
                        "-t", "raw"
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            else:
                # 使用PyAudio设备
                self.stream = self.pyaudio.open(
                    format=self.config["audio_format"],
                    channels=self.config["channels"],
                    rate=sample_rate,
                    input=True,
                    input_device_index=device["pyaudio_index"],
                    frames_per_buffer=self.config["chunk_size"]
                )
                
            # 验证流是否成功打开
            if device.get("is_alsa", False):
                if self.stream.poll() is not None:
                    logger.error("ALSA音频流未激活")
                    self.close_device()
                    return False
            else:
                if not self.stream.is_active():
                    logger.error("PyAudio音频流未激活")
                    self.close_device()
                    return False
                
            self.active_device = device
            logger.info(f"成功打开音频设备")
            return True
            
        except Exception as e:
            logger.error(f"打开音频设备出错: {e}")
            self.close_device()
            return False
            
    def close_device(self) -> None:
        """关闭当前音频设备"""
        if self.stream:
            try:
                if self.active_device and self.active_device.get("is_alsa", False):
                    # 关闭ALSA设备
                    self.stream.terminate()
                    self.stream.wait()
                else:
                    # 关闭PyAudio设备
                    self.stream.stop_stream()
                    self.stream.close()
                self.stream = None
                self.active_device = None
                logger.info("关闭音频设备")
            except Exception as e:
                logger.error(f"关闭音频设备出错: {e}")
                
    def start_recording(self) -> bool:
        """开始录制
        
        Returns:
            是否成功
        """
        if self.recording:
            logger.warning("录制已经在进行中")
            return False
            
        if not self.stream or not self.active_device:
            logger.error("未打开音频设备")
            return False
            
        # 重置停止事件
        self.stop_event.clear()
        self.recording = True
        
        # 启动录制线程
        self.record_thread = threading.Thread(target=self._record_thread)
        self.record_thread.daemon = True
        self.record_thread.start()
        
        logger.info("开始录制")
        return True
        
    def stop(self) -> None:
        """停止录制"""
        if not self.recording:
            return
            
        # 设置停止事件
        self.stop_event.set()
        self.recording = False
        
        # 等待录制线程结束
        if self.record_thread and self.record_thread.is_alive():
            self.record_thread.join(timeout=2)
            
        logger.info("停止录制")
        
    def _record_thread(self) -> None:
        """录制线程"""
        logger.info("录制线程启动")
        
        while not self.stop_event.is_set() and self.recording:
            try:
                # 等待下一个FT8周期
                next_cycle = self._wait_for_next_ft8_cycle()
                cycle_start_str = next_cycle.strftime("%H:%M:%S")
                logger.info(f"等待 {(next_cycle - datetime.datetime.now()).total_seconds():.3f} 秒到下一个FT8周期 {cycle_start_str}...")
                
                while datetime.datetime.now() < next_cycle - datetime.timedelta(seconds=self.config["advance_seconds"]):
                    if self.stop_event.is_set() or not self.recording:
                        return
                    time.sleep(0.1)
                    
                # 开始录制
                logger.info(f"录制中... FT8周期开始于 {cycle_start_str}")
                audio_data = self._record_audio(next_cycle)
                
                if audio_data and audio_data.get("frames"):
                    # 将录制的数据放入队列
                    self.buffer_queue.put(audio_data)
                    
            except Exception as e:
                logger.error(f"录制线程出错: {e}")
                time.sleep(1)
                
        logger.info("录制线程结束")
        
    def _wait_for_next_ft8_cycle(self) -> datetime.datetime:
        """计算下一个FT8周期开始时间
        
        Returns:
            下一个周期开始时间
        """
        now = datetime.datetime.now()
        minute = now.minute
        second = now.second
        
        # FT8周期每15秒一次: 00, 15, 30, 45
        next_second = (second // 15) * 15 + 15
        
        # 处理进位
        if next_second >= 60:
            next_second = 0
            minute += 1
            
        if minute >= 60:
            minute = 0
            
        next_cycle = now.replace(minute=minute, second=next_second, microsecond=0)
        
        # 如果计算的时间已经过去，加15秒
        if next_cycle <= now:
            next_cycle += datetime.timedelta(seconds=15)
            
        return next_cycle
        
    def _record_audio(self, cycle_start: datetime.datetime) -> Dict[str, Any]:
        """录制音频
        
        Args:
            cycle_start: 周期开始时间
            
        Returns:
            录制的音频数据
        """
        if not self.stream or not self.active_device:
            logger.error("未打开音频设备")
            return None
            
        try:
            # 准备录制参数
            CHUNK = self.config["chunk_size"]
            FORMAT = self.config["audio_format"]
            CHANNELS = self.config["channels"]
            RATE = self.config["sample_rate"]
            RECORD_SECONDS = self.config["record_seconds"]
            
            frames = []
            frame_count = 0
            
            # 计算总帧数
            total_frames = int(RATE / CHUNK * RECORD_SECONDS)
            
            # 使用绝对时间控制录制结束
            record_start = time.time()
            record_end_time = record_start + RECORD_SECONDS
            
            # 录制音频
            while time.time() < record_end_time and frame_count < total_frames:
                if self.stop_event.is_set() or not self.recording:
                    break
                    
                try:
                    # 计算剩余时间
                    remaining = record_end_time - time.time()
                    if remaining <= 0:
                        break
                        
                    # 读取一块音频数据
                    if self.active_device.get("is_alsa", False):
                        # 从ALSA设备读取数据
                        data = self.stream.stdout.read(CHUNK * 2)  # 16位采样，每个样本2字节
                        if not data:
                            break
                    else:
                        # 从PyAudio设备读取数据
                        data = self.stream.read(CHUNK, exception_on_overflow=False)
                        
                    frames.append(data)
                    frame_count += 1
                except Exception as e:
                    logger.error(f"读取音频数据出错: {e}")
                    time.sleep(0.001)  # 短暂休息避免CPU过载
                    continue  # 错误后继续尝试读取
                    
            actual_record_time = time.time() - record_start
            
            # 只要获取了一定比例的数据就可以继续处理
            if frame_count < total_frames * 0.7:  # 70%
                logger.warning(f"录制不完整: 获取 {frame_count}/{total_frames} 帧")
                if frame_count < total_frames * 0.5:  # 50%
                    logger.error("录制数据太少，丢弃")
                    return None
                else:
                    # 帧数介于50%-70%之间，尝试处理但记录警告
                    logger.warning("尝试解码部分录制数据")
                    
            # 准备返回的数据
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            cycle_start_str = cycle_start.strftime("%Y%m%d_%H%M%S")
            
            return {
                "frames": frames,
                "frame_count": frame_count,
                "total_frames": total_frames,
                "timestamp": timestamp,
                "cycle_start": cycle_start_str,
                "sample_rate": RATE,
                "channels": CHANNELS,
                "sample_width": self.pyaudio.get_sample_size(FORMAT),
                "format": FORMAT,
                "actual_duration": actual_record_time,
                "device": self.active_device
            }
            
        except Exception as e:
            logger.error(f"录制音频出错: {e}")
            return None
            
    def save_audio_file(self, audio_data: Dict[str, Any], filename: str = None) -> Optional[str]:
        """保存音频数据为WAV文件
        
        Args:
            audio_data: 音频数据
            filename: 文件名，如果为None则使用时间戳
            
        Returns:
            保存的文件路径
        """
        if not audio_data or not audio_data.get("frames"):
            return None
            
        try:
            # 准备文件名
            if not filename:
                timestamp = audio_data.get("timestamp", datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
                filename = f"recording_{timestamp}.wav"
                
            # 确保文件扩展名正确
            if not filename.lower().endswith(".wav"):
                filename += ".wav"
                
            # 确保输出目录存在
            os.makedirs(self.config["output_dir"], exist_ok=True)
                
            # 准备文件路径
            filepath = os.path.join(self.config["output_dir"], filename)
            
            # 保存WAV文件
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(audio_data["channels"])
                wf.setsampwidth(audio_data["sample_width"])
                wf.setframerate(audio_data["sample_rate"])
                wf.writeframes(b''.join(audio_data["frames"]))
                
            logger.info(f"保存音频文件: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"保存音频文件出错: {e}")
            return None
            
    def get_next_audio(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """从缓冲队列获取下一个音频数据
        
        Args:
            timeout: 超时时间，秒
            
        Returns:
            音频数据，如果队列为空则返回None
        """
        try:
            return self.buffer_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def is_buffer_empty(self) -> bool:
        """检查缓冲队列是否为空
        
        Returns:
            是否为空
        """
        return self.buffer_queue.empty()
        
    def get_buffer_size(self) -> int:
        """获取缓冲队列大小
        
        Returns:
            队列大小
        """
        return self.buffer_queue.qsize() 