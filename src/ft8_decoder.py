#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FT8解码器接口模块

该模块提供与FT8解码器的交互接口
"""

import os
import subprocess
import logging
import datetime
import re
import time
from typing import List, Dict, Any, Optional, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('FT8Decoder')

class FT8Decoder:
    """FT8解码器类"""
    
    def __init__(self, decoder_path: str = None):
        """初始化FT8解码器
        
        Args:
            decoder_path: FT8解码器路径，默认在环境变量中查找
        """
        self.decoder_path = decoder_path
        if not self.decoder_path:
            # 尝试在当前路径或环境变量PATH中查找
            self.decoder_path = self._find_decoder()
            
        # 验证解码器是否可用
        if not self._validate_decoder():
            raise ValueError(f"无法找到有效的FT8解码器: {self.decoder_path}")
            
        logger.info(f"FT8解码器初始化完成，使用: {self.decoder_path}")
    
    def _find_decoder(self) -> str:
        """查找FT8解码器
        
        Returns:
            解码器路径
        """
        # 首先检查当前项目目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        search_paths = [
            # 在项目内部查找
            os.path.join(current_dir, "..", "ft8decoder", "ref", "ft8.py"),
            # 如果项目在wsjtx-2.7.0目录下
            os.path.join(current_dir, "..", "..", "ft8decoder", "ref", "ft8.py"),
            # 标准路径
            "./ft8decoder/ref/ft8.py",
            "../ft8decoder/ref/ft8.py",
            # 绝对路径
            "/opt/metagpt/workspace/wsjt/wsjtx-2.7.0/FT8PYCLI/ft8decoder/ref/ft8.py",
            "/opt/metagpt/workspace/wsjt/wsjtx-2.7.0/ft8decoder/ref/ft8.py",
        ]
        
        for path in search_paths:
            if os.path.exists(path):
                logger.info(f"找到FT8解码器: {path}")
                return os.path.abspath(path)
        
        # 如果没有找到，尝试使用环境变量中的解码器
        logger.warning("未在标准位置找到FT8解码器，请手动指定decoder_path参数")
        return "ft8.py"  # 默认假设在PATH中可用
    
    def _validate_decoder(self) -> bool:
        """验证解码器是否可用
        
        Returns:
            是否可用
        """
        if not os.path.exists(self.decoder_path):
            logger.error(f"解码器文件不存在: {self.decoder_path}")
            return False
            
        # 尝试运行一下解码器，看是否正常
        try:
            ref_dir = os.path.dirname(self.decoder_path)
            cmd = f"cd {ref_dir} && python3 {os.path.basename(self.decoder_path)} -h"
            process = subprocess.Popen(
                cmd, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(timeout=3)
            
            # 检查是否正常运行 - 即使返回错误码，只要输出了帮助信息就认为解码器有效
            # 有些命令行工具在显示帮助时会返回错误码1
            has_output = stdout.strip() or stderr.strip()
            has_usage = "usage" in (stdout + stderr).lower() or "-file" in (stdout + stderr).lower()
            
            if has_output and (has_usage or "ft8" in (stdout + stderr).lower()):
                logger.info(f"验证FT8解码器成功: {self.decoder_path}")
                return True
            else:
                logger.error(f"验证FT8解码器失败: {self.decoder_path}, 返回码: {process.returncode}, 输出: {stdout}, 错误: {stderr}")
                return False
        except Exception as e:
            logger.error(f"验证解码器出错: {e}")
            return False
    
    def decode_file(self, wav_file: str) -> List[Dict[str, Any]]:
        """解码WAV文件
        
        Args:
            wav_file: WAV文件路径
            
        Returns:
            解码结果列表
        """
        if not os.path.exists(wav_file):
            logger.error(f"WAV文件不存在: {wav_file}")
            return []
            
        decode_start = time.time()
        logger.info(f"开始解码: {wav_file}")
        
        # 构建解码命令
        ref_dir = os.path.dirname(self.decoder_path)
        cmd = f"cd {ref_dir} && python3 {os.path.basename(self.decoder_path)} -file {wav_file}"
        
        try:
            # 使用Popen运行解码命令并实时获取输出
            process = subprocess.Popen(
                cmd, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 解析解码结果
            messages = []
            for line in iter(process.stdout.readline, ''):
                if line.startswith('P'):
                    logger.debug(f"解码行: {line.strip()}")
                    message = self._parse_output(line.strip())
                    if message:
                        messages.append(message)
                        logger.info(f"解码消息: {message['pass']} {message['snr']:>3} {message['freq']:>7} {message['message']}")
            
            # 等待进程完成
            process.wait()
            
            # 检查是否有错误
            stderr = process.stderr.read()
            if stderr and process.returncode != 0:
                logger.error(f"解码过程出错: {stderr}")
            
            decode_time = time.time() - decode_start
            logger.info(f"解码完成，找到 {len(messages)} 条消息，耗时 {decode_time:.2f}秒")
            
            return messages
            
        except Exception as e:
            logger.error(f"解码过程中出错: {e}")
            return []
    
    def _parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """解析解码器输出
        
        Args:
            line: 一行解码输出
            
        Returns:
            解析后的消息字典
        """
        if not line:
            return None
            
        try:
            # 解析格式如: P0 - 14.0  491.5  6598 0.30 -15 CQ DU1RRE PK04
            parts = line.split()
            if len(parts) >= 8:
                pass_num = parts[0]  # P0, P1, ...
                time_offset = parts[2]  # 时间偏移
                freq = parts[3]  # 频率
                snr = parts[6]  # 信噪比
                message = " ".join(parts[7:])  # 消息内容
                
                return {
                    "time": datetime.datetime.now().strftime("%H:%M:%S"),
                    "pass": pass_num,
                    "time_offset": time_offset,
                    "freq": freq,
                    "snr": snr,
                    "message": message,
                    "raw": line
                }
            else:
                logger.warning(f"无法解析行: {line}")
                return None
        except Exception as e:
            logger.error(f"解析解码器输出出错: {e}, 行: {line}")
            return None 