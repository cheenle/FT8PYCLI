#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频处理模块

提供音频重采样和格式转换功能
"""

import os
import time
import wave
import logging
import tempfile
import hashlib
import numpy as np
import scipy.io.wavfile
import scipy.signal
from typing import Dict, Any, Optional, Tuple

# 配置日志
logger = logging.getLogger('AudioProcessor')

class AudioProcessor:
    """音频处理类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """初始化音频处理器
        
        Args:
            config: 配置字典
        """
        # 默认配置
        self.config = {
            "target_sample_rate": 12000,  # 目标采样率，FT8解码通常需要12kHz
            "temp_dir": tempfile.gettempdir(),  # 临时文件目录
            "cache_size": 10,  # 缓存大小
        }
        
        # 更新配置
        if config:
            self.config.update(config)
            
        # 初始化缓存
        self.resampling_cache = {}
            
        logger.info("音频处理器初始化完成")
        
    def resample_audio_data(self, audio_data: Dict[str, Any]) -> Optional[str]:
        """重采样音频数据
        
        Args:
            audio_data: 音频数据
            
        Returns:
            重采样后的WAV文件路径
        """
        if not audio_data or not audio_data.get("frames"):
            logger.error("无效的音频数据")
            return None
            
        try:
            # 确保临时目录存在
            os.makedirs(self.config["temp_dir"], exist_ok=True)
            
            # 计算音频内容的哈希值
            audio_bytes = b''.join(audio_data["frames"])
            audio_hash = hashlib.md5(audio_bytes[:1024*10]).hexdigest()[:8]  # 使用前10KB计算哈希
            
            # 构造缓存键
            cache_key = f"{audio_hash}_{audio_data['sample_rate']}_{self.config['target_sample_rate']}"
            
            # 检查缓存
            if cache_key in self.resampling_cache:
                cache_path = self.resampling_cache[cache_key]
                if os.path.exists(cache_path):
                    logger.debug(f"使用缓存的重采样数据: {cache_path}")
                    return cache_path
                else:
                    # 缓存文件不存在，删除缓存项
                    del self.resampling_cache[cache_key]
                    
            # 准备临时文件名
            timestamp = audio_data.get("timestamp", time.strftime("%Y%m%d_%H%M%S"))
            temp_base = f"temp_{timestamp}_{audio_hash}"
            
            # 临时文件路径
            temp_wav = os.path.join(self.config["temp_dir"], f"{temp_base}.wav")
            temp_resampled_wav = os.path.join(self.config["temp_dir"], f"{temp_base}_resampled.wav")
            
            # 检查是否需要重采样
            if audio_data["sample_rate"] == self.config["target_sample_rate"]:
                # 不需要重采样，直接保存原始音频
                with wave.open(temp_wav, 'wb') as wf:
                    wf.setnchannels(audio_data["channels"])
                    wf.setsampwidth(audio_data["sample_width"])
                    wf.setframerate(audio_data["sample_rate"])
                    wf.writeframes(audio_bytes)
                logger.debug(f"不需要重采样，保存原始音频: {temp_wav}")
                
                # 添加到缓存
                self._add_to_cache(cache_key, temp_wav)
                return temp_wav
                
            # 需要重采样
            logger.info(f"重采样从 {audio_data['sample_rate']}Hz 到 {self.config['target_sample_rate']}Hz")
            
            # 保存原始WAV文件
            with wave.open(temp_wav, 'wb') as wf:
                wf.setnchannels(audio_data["channels"])
                wf.setsampwidth(audio_data["sample_width"])
                wf.setframerate(audio_data["sample_rate"])
                wf.writeframes(audio_bytes)
                
            # 读取原始WAV文件
            try:
                rate, data = scipy.io.wavfile.read(temp_wav)
                
                # 计算重采样比例
                resample_ratio = self.config["target_sample_rate"] / rate
                
                # 计算新长度
                new_length = int(len(data) * resample_ratio)
                
                # 使用scipy的重采样函数
                resampled_data = scipy.signal.resample(data, new_length)
                
                # 保存重采样后的WAV文件
                scipy.io.wavfile.write(temp_resampled_wav, self.config["target_sample_rate"], 
                                       resampled_data.astype(np.int16))
                                       
                # 删除原始临时文件
                try:
                    os.remove(temp_wav)
                except:
                    pass
                    
                # 添加到缓存
                self._add_to_cache(cache_key, temp_resampled_wav)
                
                logger.debug(f"重采样完成: {temp_resampled_wav}")
                return temp_resampled_wav
            except Exception as e:
                logger.error(f"重采样过程中出错: {e}")
                # 返回原始WAV文件作为备用
                logger.warning(f"使用原始文件作为备用: {temp_wav}")
                return temp_wav
            
        except Exception as e:
            logger.error(f"重采样音频数据出错: {e}")
            return None
            
    def _add_to_cache(self, key: str, value: str) -> None:
        """添加到缓存
        
        Args:
            key: 缓存键
            value: 缓存值
        """
        # 限制缓存大小
        if len(self.resampling_cache) >= self.config["cache_size"]:
            # 删除最旧的缓存项
            old_key = next(iter(self.resampling_cache))
            old_file = self.resampling_cache.pop(old_key)
            try:
                if os.path.exists(old_file):
                    os.remove(old_file)
            except:
                pass
                
        # 添加新缓存项
        self.resampling_cache[key] = value
        
    def resample_file(self, input_file: str, output_file: str = None, target_rate: int = None) -> Optional[str]:
        """重采样WAV文件
        
        Args:
            input_file: 输入WAV文件路径
            output_file: 输出WAV文件路径，如果为None则自动生成
            target_rate: 目标采样率，如果为None则使用配置的目标采样率
            
        Returns:
            重采样后的WAV文件路径
        """
        if not os.path.exists(input_file):
            logger.error(f"输入文件不存在: {input_file}")
            return None
            
        try:
            # 计算文件哈希值
            with open(input_file, 'rb') as f:
                file_hash = hashlib.md5(f.read(1024*1024)).hexdigest()[:8]  # 使用前1MB计算哈希
                
            # 读取原始WAV文件信息
            with wave.open(input_file, 'rb') as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                
            # 目标采样率
            if target_rate is None:
                target_rate = self.config["target_sample_rate"]
                
            # 构造缓存键
            cache_key = f"{file_hash}_{framerate}_{target_rate}"
            
            # 检查缓存
            if cache_key in self.resampling_cache:
                cache_path = self.resampling_cache[cache_key]
                if os.path.exists(cache_path):
                    logger.debug(f"使用缓存的重采样文件: {cache_path}")
                    return cache_path
                else:
                    # 缓存文件不存在，删除缓存项
                    del self.resampling_cache[cache_key]
                    
            # 检查是否需要重采样
            if framerate == target_rate:
                logger.debug(f"不需要重采样: {input_file}")
                return input_file
                
            # 准备输出文件名
            if output_file is None:
                basename = os.path.basename(input_file)
                output_file = os.path.join(self.config["temp_dir"], f"resampled_{target_rate}_{basename}")
                
            # 重采样
            logger.info(f"重采样文件从 {framerate}Hz 到 {target_rate}Hz: {input_file}")
            
            # 读取原始WAV文件
            rate, data = scipy.io.wavfile.read(input_file)
            
            # 计算重采样比例
            resample_ratio = target_rate / rate
            
            # 计算新长度
            new_length = int(len(data) * resample_ratio)
            
            # 使用scipy的重采样函数
            resampled_data = scipy.signal.resample(data, new_length)
            
            # 保存重采样后的WAV文件
            scipy.io.wavfile.write(output_file, target_rate, resampled_data.astype(np.int16))
            
            # 添加到缓存
            self._add_to_cache(cache_key, output_file)
            
            logger.debug(f"重采样文件完成: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"重采样文件出错: {e}")
            return None
            
    def clear_cache(self) -> None:
        """清理缓存"""
        for cache_path in self.resampling_cache.values():
            try:
                if os.path.exists(cache_path):
                    os.remove(cache_path)
            except:
                pass
                
        self.resampling_cache.clear()
        logger.info("缓存已清理") 