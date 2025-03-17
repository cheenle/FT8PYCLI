# FT8PYCLI

FT8PYCLI 是一个命令行工具，用于实时解码 FT8 数字模式信号。它支持从声卡或音频文件中读取信号并进行解码。

## 功能特点

- 实时从声卡录制音频并解码 FT8 信号
- 支持从 WAV 文件读取并解码
- 自动同步 FT8 时间周期（每15秒一个周期）
- 支持多种采样率和音频设备
- 解码结果实时显示和日志记录

## 系统要求

- Python 3.7+
- Linux/macOS/Windows
- 支持的声卡设备（内置声卡或USB声卡）
- 足够的CPU处理能力（建议至少双核）

## 安装

1. 安装系统依赖：

   Ubuntu/Debian:
   ```bash
   sudo apt-get update
   sudo apt-get install python3-dev portaudio19-dev libfftw3-dev
   ```

   CentOS/RHEL:
   ```bash
   sudo yum install python3-devel portaudio-devel fftw3-devel
   ```

   macOS:
   ```bash
   brew install portaudio fftw
   ```

2. 克隆仓库：
   ```bash
   git clone https://github.com/cheenlie/FT8PYCLI.git
   cd FT8PYCLI
   ```

3. 创建并激活虚拟环境（推荐）：
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/macOS
   # 或
   venv\Scripts\activate  # Windows
   ```

4. 安装 Python 依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 使用方法

### 1. 准备工作

1. 确保系统时间准确（FT8解码对时间同步要求较高）：
   ```bash
   # Linux/macOS
   ntpdate pool.ntp.org  # 需要root权限
   # 或
   sudo systemctl restart systemd-timesyncd  # systemd系统
   ```

2. 创建必要的目录：
   ```bash
   mkdir -p logs recordings temp
   ```

3. 创建配置文件：
   ```bash
   cp config/ft8pycli.json.example config/ft8pycli.json
   ```

### 2. 查看可用音频设备

```bash
python src/ft8pycli.py --list-devices
```

输出示例：
```
可用音频设备:
[0] 内置音频 (2 通道)
[1] USB Audio Device (2 通道)
[2] Virtual Cable Input (2 通道)
```

### 3. 实时解码

1. 基本使用（使用默认设备）：
   ```bash
   python src/ft8pycli.py
   ```

2. 指定音频设备：
   ```bash
   python src/ft8pycli.py --device "1,0"  # 使用设备1的左声道
   # 或
   python src/ft8pycli.py --device "1,1"  # 使用设备1的右声道
   ```

3. 指定采样率：
   ```bash
   python src/ft8pycli.py --device "1,0" --sample-rate 48000
   ```

4. 保存录音文件：
   ```bash
   python src/ft8pycli.py --device "1,0" --save-audio
   ```

### 4. 从WAV文件解码

1. 解码单个文件：
   ```bash
   python src/ft8pycli.py --file recordings/ft8_signal.wav
   ```

2. 批量解码目录中的文件：
   ```bash
   python src/ft8pycli.py --dir recordings/
   ```

### 5. 高级选项

1. 调整日志级别：
   ```bash
   python src/ft8pycli.py --log-level DEBUG
   ```

2. 指定配置文件：
   ```bash
   python src/ft8pycli.py --config my_config.json
   ```

3. 设置解码频率范围：
   ```bash
   python src/ft8pycli.py --min-freq 500 --max-freq 3000
   ```

## 配置文件说明

配置文件 `config/ft8pycli.json` 支持以下参数：

```json
{
    "audio": {
        "device": "1,0",           // 音频设备和通道
        "sample_rate": 48000,      // 采样率
        "channels": 1,             // 通道数
        "chunk_size": 1024         // 缓冲区大小
    },
    "decoder": {
        "target_sample_rate": 12000,  // FT8解码采样率
        "min_freq": 500,              // 最小解码频率
        "max_freq": 3000,             // 最大解码频率
        "threshold": -26              // 解码阈值(dB)
    },
    "recording": {
        "save_audio": false,          // 是否保存录音
        "output_dir": "recordings",   // 录音保存目录
        "record_seconds": 13.5,       // 录制时长
        "advance_seconds": 0.2        // 提前开始录制的时间
    },
    "logging": {
        "level": "INFO",             // 日志级别
        "file": "logs/ft8pycli.log"  // 日志文件
    }
}
```

## 常见问题

1. 没有声音输入
   - 检查音频设备是否正确连接
   - 使用 `--list-devices` 确认设备是否被识别
   - 检查设备音量和系统音量设置

2. 解码不出信号
   - 确保系统时间准确同步
   - 检查音频电平是否合适（使用 `--show-levels` 选项）
   - 尝试调整解码阈值（使用 `--threshold` 选项）

3. 采样率错误
   - 某些声卡可能不支持特定采样率
   - 使用 `--list-devices` 查看设备支持的采样率
   - 尝试使用常用采样率：48000, 44100, 96000

## 性能优化

1. 降低 CPU 使用率：
   ```bash
   python src/ft8pycli.py --optimize-cpu
   ```

2. 减少内存使用：
   ```bash
   python src/ft8pycli.py --low-memory
   ```

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request！在提交之前，请：

1. 确保代码通过测试：
   ```bash
   python -m pytest tests/
   ```

2. 确保代码风格符合规范：
   ```bash
   flake8 src/
   ```

## 致谢

- 感谢 WSJT-X 项目提供的 FT8 协议规范
- 感谢所有贡献者的支持 