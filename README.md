# FT8PYCLI

FT8PYCLI 是一个基于 Python 的 FT8 信号解码命令行工具，支持实时录音和解码 FT8 信号。

## 功能特点

- 支持实时录音和解码 FT8 信号
- 支持多种音频输入设备（包括 USB 设备）
- 自动检测和配置音频设备
- 支持保存录音文件
- 详细的日志记录
- 配置文件支持

## 系统要求

- Python 3.6 或更高版本
- ALSA 音频系统（Linux）
- 支持音频输入的 USB 设备（可选）

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

## 配置

1. 复制配置文件模板：
```bash
cp config/ft8pycli.json.example config/ft8pycli.json
```

2. 编辑配置文件 `config/ft8pycli.json`，根据需要修改以下参数：
- `sample_rate`: 采样率（默认：44100）
- `channels`: 声道数（默认：1）
- `record_seconds`: 录音时长（默认：13.5秒）
- `advance_seconds`: 提前开始录音的时间（默认：0.2秒）
- `temp_dir`: 临时文件目录
- `output_dir`: 录音输出目录

## 使用方法

1. 列出可用设备：
```bash
python src/ft8pycli.py
```

2. 开始实时录音和解码：
```bash
python src/ft8pycli.py live <设备索引>
```

3. 解码音频文件：
```bash
python src/ft8pycli.py decode <音频文件路径>
```

## 目录结构

```
FT8PYCLI/
├── config/             # 配置文件目录
├── docs/              # 文档
├── ft8decoder/        # FT8解码器
├── logs/              # 日志文件
├── recordings/        # 录音文件
├── src/               # 源代码
├── tests/             # 测试文件
└── temp/              # 临时文件
```

## 开发

1. 运行测试：
```bash
python -m pytest tests/
```

2. 代码风格检查：
```bash
flake8 src/
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 致谢

- [WSJT-X](https://physics.princeton.edu/pulsar/k1jt/wsjtx.html) - FT8 协议和参考实现
- [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) - 音频处理库 