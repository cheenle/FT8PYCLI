#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FT8PYCLI - FT8解码命令行工具

整合FT8解码器、音频录制和处理功能的命令行工具
"""

import os
import sys
import time
import logging
import threading
import queue
import signal
import argparse
import datetime
import json
import concurrent.futures
from typing import Dict, Any, List, Optional
import readline
import tempfile

# 添加当前目录到模块搜索路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入自定义模块
from ft8_decoder import FT8Decoder
from audio_recorder import AudioRecorder
from audio_processor import AudioProcessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../logs/ft8pycli.log"))
    ]
)
logger = logging.getLogger('FT8PYCLI')

# 确保日志目录存在
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../logs"), exist_ok=True)

# 默认配置
DEFAULT_CONFIG = {
    "decoder_path": None,  # 自动查找
    "target_sample_rate": 12000,  # FT8解码目标采样率
    "record_seconds": 13.5,  # 录制时长
    "advance_seconds": 0.2,  # 提前开始录制的时间
    "output_dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "../recordings"),
    "temp_dir": None,  # 使用系统临时目录
    "log_level": "INFO",
    "parallel_decoding": True,  # 是否使用并行解码
    "max_workers": 3,  # 最大工作线程数
    "save_recordings": False,  # 是否保存录音文件
    "save_decoded": True,  # 是否保存解码结果
}

class FT8PYCLI:
    """FT8PYCLI主类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """初始化FT8PYCLI
        
        Args:
            config: 配置字典
        """
        # 默认配置
        self.config = {
            "temp_dir": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp"),  # 临时文件目录
            "output_dir": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recordings"),  # 输出目录
            "save_recordings": False,  # 是否保存录音
            "save_decoded": False,  # 是否保存解码结果
            "parallel_decoding": True,  # 是否并行解码
            "max_workers": 3,  # 最大工作线程数
            "log_level": "INFO",  # 日志级别
            "buffer_size": 4,  # 缓冲区大小
            "advance_seconds": 0.5,  # 提前开始录制的秒数
            "target_sample_rate": 12000,  # 目标采样率，FT8解码通常需要12kHz
            "auto_start": False,  # 是否自动开始实时解码
            "auto_device": None,  # 自动选择的设备ID
            "record_seconds": 13.5,  # 录音时长
        }
        
        # 更新配置
        if config:
            self.config.update(config)
        
        # 确保temp_dir不为None
        if self.config["temp_dir"] is None:
            self.config["temp_dir"] = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")
            
        # 确保必要的目录存在
        os.makedirs(self.config["output_dir"], exist_ok=True)
        os.makedirs(os.path.join(self.config["output_dir"], "decoded"), exist_ok=True)
        os.makedirs(self.config["temp_dir"], exist_ok=True)

        # 设置日志级别
        logging.getLogger().setLevel(getattr(logging, self.config["log_level"]))

        # 初始化FT8解码器
        self.decoder = FT8Decoder()
        
        # 初始化音频处理器，用于重采样
        self.audio_processor = AudioProcessor({
            "temp_dir": self.config["temp_dir"],
            "target_sample_rate": self.config["target_sample_rate"],
            "cache_size": 20,  # 适当增加缓存大小
        })
        
        # 初始化音频录制器
        self.recorder = AudioRecorder({
            "output_dir": self.config["output_dir"],
            "buffer_size": self.config["buffer_size"],
            "advance_seconds": self.config["advance_seconds"],
            "record_seconds": self.config["record_seconds"],
        })
        
        # 初始化线程池
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.config["max_workers"])
        
        # 初始化状态变量
        self.running = False
        self.stop_event = threading.Event()
        self.decode_thread = None
        self.messages = []
        self.messages_lock = threading.Lock()
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        
        logger.info("FT8PYCLI初始化完成，日志级别: " + self.config["log_level"])
        
    def _signal_handler(self, sig, frame):
        """信号处理器
        
        处理Ctrl+C等信号
        """
        logger.info("收到中断信号，正在退出...")
        self.stop()
        
    def start(self):
        """启动FT8PYCLI
        
        开始处理命令行输入
        """
        logger.info("FT8PYCLI启动")
        
        # 打印欢迎信息
        print("\n欢迎使用FT8PYCLI - FT8解码命令行工具!")
        print("输入'help'查看帮助，输入'exit'退出程序\n")
        
        # 处理命令行输入
        while True:
            try:
                command = input("FT8PYCLI> ").strip()
                if not command:
                    continue
                    
                if command.lower() in ["exit", "quit"]:
                    break
                    
                self._process_command(command)
                
            except KeyboardInterrupt:
                print("\n收到Ctrl+C，退出程序")
                break
            except Exception as e:
                logger.error(f"处理命令时出错: {e}")
                
        # 退出前停止所有任务
        self.stop()
        logger.info("FT8PYCLI退出")
        
    def stop(self):
        """停止FT8PYCLI
        
        停止所有线程和任务
        """
        if not self.running:
            return
            
        # 设置停止事件
        self.stop_event.set()
        self.running = False
        
        # 停止录制
        self.recorder.stop()
        
        # 等待解码线程结束
        if self.decode_thread and self.decode_thread.is_alive():
            self.decode_thread.join(timeout=2)
            
        # 关闭线程池
        self.executor.shutdown(wait=False)
        
        # 清理缓存
        self.audio_processor.clear_cache()
        
        logger.info("FT8PYCLI已停止")
        
    def _process_command(self, command: str):
        """处理命令
        
        Args:
            command: 命令行输入
        """
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:]
        
        # 命令处理
        if cmd == "help":
            self._print_help()
        elif cmd == "list":
            self._list_devices()
        elif cmd == "decode":
            if len(args) < 1:
                print("错误: 缺少文件路径参数")
                print("用法: decode <wav_file>")
                return
            self._decode_file(args[0])
        elif cmd == "batch":
            if len(args) < 1:
                print("错误: 缺少目录路径参数")
                print("用法: batch <directory>")
                return
            self._batch_decode(args[0])
        elif cmd == "live":
            if len(args) < 1:
                print("错误: 缺少设备ID参数")
                print("用法: live <device_id>")
                return
            try:
                device_id = int(args[0])
                self._start_live_decode(device_id)
            except ValueError:
                print(f"错误: 设备ID必须是整数，而不是 '{args[0]}'")
        elif cmd == "stop":
            self._stop_live_decode()
        elif cmd == "info":
            self._show_info()
        elif cmd == "clear":
            self._clear_messages()
        elif cmd == "save":
            if len(args) < 1:
                print("错误: 缺少文件路径参数")
                print("用法: save <file_path>")
                return
            self._save_messages(args[0])
        elif cmd == "config":
            if len(args) < 1:
                self._show_config()
            elif len(args) >= 2:
                self._set_config(args[0], " ".join(args[1:]))
            else:
                print("错误: 缺少参数")
                print("用法: config [key] [value]")
        else:
            print(f"未知命令: {cmd}")
            print("输入'help'查看可用命令")
            
    def _print_help(self):
        """打印帮助信息"""
        print("\nFT8PYCLI 帮助:")
        print("  help                - 显示此帮助信息")
        print("  list                - 列出可用的音频设备")
        print("  decode <file>       - 解码指定的WAV文件")
        print("  batch <directory>   - 批量解码目录中的WAV文件")
        print("  live <device_id>    - 使用指定设备进行实时解码")
        print("  stop                - 停止实时解码")
        print("  info                - 显示当前状态信息")
        print("  clear               - 清空已解码的消息")
        print("  save <file>         - 保存解码的消息到文件")
        print("  config              - 显示当前配置")
        print("  config <key> <value>- 设置配置项")
        print("  exit                - 退出程序")
        print()
        
    def _list_devices(self):
        """列出可用的音频设备"""
        devices = self.recorder.list_devices()
        
        if not devices:
            print("未找到可用的音频输入设备")
            return
            
        print("\n可用的音频输入设备:")
        for device in devices:
            print(f"  ID: {device['index']}, 名称: {device['name']}")
            print(f"     通道数: {device['channels']}, 默认采样率: {device['default_sample_rate']}Hz")
            print(f"     支持的采样率: {', '.join(map(str, device['supported_rates']))}Hz")
            print()
            
    def _decode_file(self, file_path: str):
        """解码单个WAV文件
        
        Args:
            file_path: WAV文件路径
        """
        if not os.path.exists(file_path):
            print(f"错误: 文件不存在: {file_path}")
            return
            
        print(f"解码: {file_path}")
        
        # 检查是否需要重采样
        with wave.open(file_path, 'rb') as wf:
            sample_rate = wf.getframerate()
            
        if sample_rate != self.config["target_sample_rate"]:
            print(f"重采样从 {sample_rate}Hz 到 {self.config['target_sample_rate']}Hz")
            resampled_file = self.audio_processor.resample_file(file_path)
            if not resampled_file:
                print("重采样失败")
                return
            file_path = resampled_file
            
        # 解码文件
        start_time = time.time()
        messages = self.decoder.decode_file(file_path)
        decode_time = time.time() - start_time
        
        # 打印解码结果
        if messages:
            print(f"\n找到 {len(messages)} 条消息:")
            for msg in messages:
                print(f"  {msg['pass']} {msg['snr']:>3} {msg['freq']:>7} {msg['message']}")
            
            # 添加到消息列表
            with self.messages_lock:
                self.messages.extend(messages)
                
            # 保存解码结果
            if self.config["save_decoded"]:
                output_dir = os.path.join(self.config["output_dir"], "decoded")
                os.makedirs(output_dir, exist_ok=True)
                
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = os.path.join(output_dir, f"decoded_{timestamp}_{os.path.basename(file_path)}.txt")
                
                with open(output_file, 'w') as f:
                    for msg in messages:
                        f.write(f"{msg['pass']} {msg['snr']} {msg['freq']} {msg['message']}\n")
                        
                print(f"解码结果已保存到: {output_file}")
        else:
            print("未找到解码消息")
            
        print(f"解码完成，耗时 {decode_time:.2f}秒")
        
    def _batch_decode(self, directory: str):
        """批量解码目录中的WAV文件
        
        Args:
            directory: 目录路径
        """
        if not os.path.isdir(directory):
            print(f"错误: 目录不存在: {directory}")
            return
            
        # 查找目录中的WAV文件
        wav_files = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith('.wav'):
                    wav_files.append(os.path.join(root, file))
                    
        if not wav_files:
            print(f"目录中没有WAV文件: {directory}")
            return
            
        print(f"找到 {len(wav_files)} 个WAV文件，开始批量解码...")
        
        # 使用线程池并行解码
        start_time = time.time()
        results = []
        
        if self.config["parallel_decoding"]:
            # 并行解码
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.config["max_workers"]) as executor:
                futures = []
                for file_path in wav_files:
                    future = executor.submit(self._decode_file_worker, file_path)
                    futures.append(future)
                    
                # 收集结果
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        results.append(result)
        else:
            # 串行解码
            for file_path in wav_files:
                result = self._decode_file_worker(file_path)
                if result:
                    results.append(result)
                    
        total_time = time.time() - start_time
        
        # 合并所有消息
        all_messages = []
        for result in results:
            all_messages.extend(result["messages"])
            
        # 添加到消息列表
        with self.messages_lock:
            self.messages.extend(all_messages)
            
        # 汇总结果
        print(f"\n批量解码完成，耗时 {total_time:.2f}秒")
        print(f"解码了 {len(results)} 个文件，找到 {len(all_messages)} 条消息")
        
    def _decode_file_worker(self, file_path: str) -> Optional[Dict[str, Any]]:
        """解码文件工作线程
        
        Args:
            file_path: WAV文件路径
            
        Returns:
            解码结果
        """
        try:
            # 检查是否需要重采样
            with wave.open(file_path, 'rb') as wf:
                sample_rate = wf.getframerate()
                
            if sample_rate != self.config["target_sample_rate"]:
                logger.debug(f"重采样文件: {file_path}")
                resampled_file = self.audio_processor.resample_file(file_path)
                if not resampled_file:
                    logger.error(f"重采样失败: {file_path}")
                    return None
                file_path = resampled_file
                
            # 解码文件
            logger.debug(f"解码文件: {file_path}")
            start_time = time.time()
            messages = self.decoder.decode_file(file_path)
            decode_time = time.time() - start_time
            
            return {
                "file": file_path,
                "messages": messages,
                "decode_time": decode_time
            }
        except Exception as e:
            logger.error(f"解码文件出错: {file_path}, 错误: {e}")
            return None
            
    def _start_live_decode(self, device_id: int):
        """开始实时解码
        
        Args:
            device_id: 音频设备ID
        """
        if self.running:
            print("实时解码已经在运行中，请先停止")
            return
            
        # 打开音频设备
        if not self.recorder.open_device(device_id):
            print(f"无法打开音频设备: {device_id}")
            return
            
        # 启动录制
        if not self.recorder.start_recording():
            print("启动录制失败")
            return
            
        # 重置停止事件
        self.stop_event.clear()
        self.running = True
        
        # 启动解码线程
        self.decode_thread = threading.Thread(target=self._decode_worker_thread)
        self.decode_thread.daemon = True
        self.decode_thread.start()
        
        print(f"已启动实时解码，使用设备: {device_id}")
        
    def _stop_live_decode(self):
        """停止实时解码"""
        if not self.running:
            print("实时解码未运行")
            return
            
        # 设置停止事件
        self.stop_event.set()
        self.running = False
        
        # 停止录制
        self.recorder.stop()
        
        # 等待解码线程结束
        if self.decode_thread and self.decode_thread.is_alive():
            self.decode_thread.join(timeout=2)
            
        print("已停止实时解码")
        
    def _decode_worker_thread(self):
        """解码工作线程"""
        logger.info("解码工作线程启动")
        
        # 使用集合追踪正在处理的任务
        active_futures = set()
        
        while not self.stop_event.is_set() and self.running:
            try:
                # 清理已完成的任务
                done_futures = {f for f in active_futures if f.done()}
                active_futures -= done_futures
                
                # 检查是否有容量处理新任务
                if len(active_futures) >= self.config["max_workers"]:
                    time.sleep(0.1)
                    continue
                    
                # 从录音器获取音频数据
                audio_data = self.recorder.get_next_audio(timeout=0.5)
                if not audio_data:
                    # 队列为空，继续等待
                    continue
                    
                # 提交到线程池中执行
                if self.config["parallel_decoding"]:
                    future = self.executor.submit(self._process_audio_data, audio_data)
                    active_futures.add(future)
                else:
                    # 串行处理
                    self._process_audio_data(audio_data)
                    
            except Exception as e:
                logger.error(f"解码工作线程出错: {e}")
                time.sleep(0.5)
                
        logger.info("解码工作线程结束")
        
    def _process_audio_data(self, audio_data: Dict[str, Any]):
        """处理音频数据
        
        Args:
            audio_data: 音频数据
        """
        try:
            # 检查音频数据有效性
            if not audio_data or not audio_data.get("frames"):
                logger.error("无效的音频数据，跳过处理")
                return
                
            timestamp = audio_data["timestamp"]
            wav_file = None
            
            # 保存原始录音
            if self.config["save_recordings"]:
                wav_file = self.recorder.save_audio_file(audio_data, f"recording_{timestamp}.wav")
                logger.debug(f"保存录音: {wav_file}")
            
            # 重采样音频数据
            resampled_wav = self.audio_processor.resample_audio_data(audio_data)
            if not resampled_wav:
                logger.error("重采样音频数据失败")
                # 如果已有保存的原始WAV文件，尝试直接使用
                if wav_file and os.path.exists(wav_file):
                    logger.warning(f"尝试使用原始录音文件: {wav_file}")
                else:
                    logger.error("没有可用的音频文件，跳过处理")
                    return
            else:
                # 使用重采样后的文件
                wav_file = resampled_wav
                
            # 确认文件存在
            if not os.path.exists(wav_file):
                logger.error(f"WAV文件不存在: {wav_file}")
                return
                
            # 解码WAV文件
            cycle_start = audio_data["cycle_start"]
            logger.info(f"开始解码 {cycle_start} 的数据...")
            
            start_time = time.time()
            messages = self.decoder.decode_file(wav_file)
            decode_time = time.time() - start_time
            
            # 打印解码结果
            if messages:
                print(f"解码完成，周期 {cycle_start}, 找到 {len(messages)} 条消息")
                
                # 添加到消息列表
                with self.messages_lock:
                    self.messages.extend(messages)
                    
                # 保存解码结果
                if self.config["save_decoded"]:
                    output_dir = os.path.join(self.config["output_dir"], "decoded")
                    os.makedirs(output_dir, exist_ok=True)
                    
                    output_file = os.path.join(output_dir, f"decoded_{audio_data['timestamp']}_{os.path.basename(wav_file)}.txt")
                    
                    with open(output_file, 'w') as f:
                        for msg in messages:
                            f.write(f"{msg['pass']} {msg['snr']} {msg['freq']} {msg['message']}\n")
                            
                    logger.info(f"解码结果已保存到: {output_file}")
            else:
                print(f"解码完成，周期 {cycle_start}, 未找到消息")
                
            logger.info(f"解码处理完成，周期 {cycle_start}, 耗时 {decode_time:.2f}秒")
            
        except Exception as e:
            logger.error(f"处理音频数据出错: {e}")
            
    def _show_info(self):
        """显示当前状态信息"""
        print("\n当前状态:")
        print(f"  运行状态: {'运行中' if self.running else '已停止'}")
        print(f"  解码消息数: {len(self.messages)}")
        
        # 显示最近的消息
        if self.messages:
            print("\n最近的10条消息:")
            for msg in self.messages[-10:]:
                print(f"  [{msg['time']}] {msg['pass']} {msg['snr']:>3} {msg['freq']:>7} {msg['message']}")
            print()
            
    def _clear_messages(self):
        """清空已解码的消息"""
        with self.messages_lock:
            count = len(self.messages)
            self.messages.clear()
            
        print(f"已清空 {count} 条消息")
        
    def _save_messages(self, file_path: str):
        """保存解码的消息到文件
        
        Args:
            file_path: 文件路径
        """
        if not self.messages:
            print("没有消息可保存")
            return
            
        try:
            # 确定文件类型
            if file_path.lower().endswith('.json'):
                # JSON格式
                with open(file_path, 'w') as f:
                    json.dump(self.messages, f, indent=2)
            else:
                # 文本格式
                with open(file_path, 'w') as f:
                    for msg in self.messages:
                        f.write(f"[{msg['time']}] {msg['pass']} {msg['snr']} {msg['freq']} {msg['message']}\n")
                        
            print(f"已保存 {len(self.messages)} 条消息到: {file_path}")
        except Exception as e:
            print(f"保存消息出错: {e}")
            
    def _show_config(self):
        """显示当前配置"""
        print("\n当前配置:")
        for key, value in self.config.items():
            print(f"  {key}: {value}")
        print()
        
    def _set_config(self, key: str, value: str):
        """设置配置项
        
        Args:
            key: 配置项名称
            value: 配置项值
        """
        if key not in self.config:
            print(f"错误: 未知的配置项 '{key}'")
            return
            
        # 类型转换
        original_value = self.config[key]
        if isinstance(original_value, bool):
            value = value.lower() in ['true', 'yes', 'y', '1', 'on']
        elif isinstance(original_value, int):
            try:
                value = int(value)
            except ValueError:
                print(f"错误: 无法将 '{value}' 转换为整数")
                return
        elif isinstance(original_value, float):
            try:
                value = float(value)
            except ValueError:
                print(f"错误: 无法将 '{value}' 转换为浮点数")
                return
                
        # 更新配置
        self.config[key] = value
        
        # 应用特殊配置
        if key == "log_level":
            logging.getLogger().setLevel(getattr(logging, value))
            
        print(f"已设置 {key} = {value}")
        
def load_config(config_file: str) -> Dict[str, Any]:
    """加载配置文件
    
    Args:
        config_file: 配置文件路径
        
    Returns:
        配置字典
    """
    config = DEFAULT_CONFIG.copy()
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                loaded_config = json.load(f)
                config.update(loaded_config)
            logger.info(f"已加载配置文件: {config_file}")
        except Exception as e:
            logger.error(f"加载配置文件出错: {e}")
            
    return config
    
def save_config(config: Dict[str, Any], config_file: str):
    """保存配置文件
    
    Args:
        config: 配置字典
        config_file: 配置文件路径
    """
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"已保存配置文件: {config_file}")
    except Exception as e:
        logger.error(f"保存配置文件出错: {e}")
        
def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="FT8PYCLI - FT8解码命令行工具")
    parser.add_argument("-c", "--config", help="配置文件路径")
    parser.add_argument("-f", "--file", help="解码指定的WAV文件")
    parser.add_argument("-d", "--device", help="指定音频设备ID进行实时解码")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志输出")
    parser.add_argument("--version", action="version", version="FT8PYCLI v1.0.0")
    
    args = parser.parse_args()
    
    # 加载配置
    config_file = args.config or os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config/ft8pycli.json")
    config = load_config(config_file)
    
    # 临时设置为DEBUG级别来诊断设备检测问题
    config["log_level"] = "DEBUG"
    
    # 更新配置
    if args.verbose:
        config["log_level"] = "DEBUG"
        
    # 设置日志级别
    logging.getLogger().setLevel(getattr(logging, config["log_level"]))
        
    # 创建FT8PYCLI实例
    ft8pycli = FT8PYCLI(config)
    
    try:
        # 如果指定了文件，直接解码
        if args.file:
            ft8pycli._decode_file(args.file)
        # 如果指定了设备，直接开始实时解码
        elif args.device:
            try:
                device_id = int(args.device)
                ft8pycli._start_live_decode(device_id)
                
                # 等待用户中断
                print("按Ctrl+C停止解码...")
                while ft8pycli.running:
                    time.sleep(0.1)
            except ValueError:
                print(f"错误: 设备ID必须是整数，而不是 '{args.device}'")
        else:
            # 否则启动交互模式
            ft8pycli.start()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在退出...")
    finally:
        # 保存配置
        save_config(config, config_file)
        
        # 停止FT8PYCLI
        ft8pycli.stop()
    
    print("FT8PYCLI已退出")
    
if __name__ == "__main__":
    # 创建必要的目录
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config"), exist_ok=True)
    
    # 启动主函数
    main() 