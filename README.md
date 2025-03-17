# FT8PYCLI

FT8PYCLI 是一个命令行工具，用于实时解码 FT8 数字模式信号。它支持从声卡或音频文件中读取信号并进行解码。

## 功能特点

- 实时从声卡录制音频并解码 FT8 信号
- 支持从 WAV 文件读取并解码
- 自动同步 FT8 时间周期
- 支持多种采样率和音频设备
- 解码结果实时显示

## 系统要求

- Python 3.7+
- Linux/macOS/Windows
- 支持的声卡设备

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/FT8PYCLI.git
cd FT8PYCLI
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 使用方法

1. 从声卡实时解码：
```bash
python src/ft8pycli.py --device "0,0"  # 使用第一个声卡的左声道
```

2. 从WAV文件解码：
```bash
python src/ft8pycli.py --file input.wav
```

3. 查看帮助：
```bash
python src/ft8pycli.py --help
```

## 配置

1. 创建配置文件：
```bash
cp config/ft8pycli.json.example config/ft8pycli.json
```

2. 编辑配置文件，设置采样率、设备等参数：
```json
{
    "target_sample_rate": 12000,
    "record_seconds": 13.5,
    "advance_seconds": 0.2
}
```

## 目录结构

```
FT8PYCLI/
├── config/             # 配置文件
├── src/               # 源代码
│   ├── ft8pycli.py    # 主程序
│   ├── ft8_decoder.py # 解码器
│   └── ...
├── logs/              # 日志文件
├── recordings/        # 录音文件
└── temp/              # 临时文件
```

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 致谢

- 感谢 WSJT-X 项目提供的 FT8 协议规范
- 感谢所有贡献者的支持 