# 贡献指南

感谢您对 FT8PYCLI 项目的关注！我们欢迎任何形式的贡献，包括但不限于：

- 代码贡献
- 文档改进
- Bug 报告
- 功能建议

## 开发环境设置

1. Fork 本仓库
2. 克隆您的 Fork：
   ```bash
   git clone https://github.com/YOUR_USERNAME/FT8PYCLI.git
   cd FT8PYCLI
   ```
3. 创建虚拟环境：
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/macOS
   # 或
   venv\Scripts\activate  # Windows
   ```
4. 安装开发依赖：
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

## 代码规范

- 遵循 PEP 8 代码风格
- 使用类型注解
- 添加适当的文档字符串
- 保持代码简洁明了

## 提交 Pull Request

1. 创建新分支：
   ```bash
   git checkout -b feature-name
   ```
2. 提交更改：
   ```bash
   git add .
   git commit -m "描述性的提交信息"
   ```
3. 推送到您的 Fork：
   ```bash
   git push origin feature-name
   ```
4. 创建 Pull Request

## 提交 Bug 报告

提交 Bug 报告时，请包含：

- 问题描述
- 复现步骤
- 期望行为
- 实际行为
- 系统环境信息
- 相关日志输出

## 开发指南

### 项目结构

```
FT8PYCLI/
├── src/               # 源代码
│   ├── ft8pycli.py    # 主程序
│   ├── ft8_decoder.py # 解码器
│   └── ...
├── tests/            # 测试文件
├── docs/             # 文档
└── config/           # 配置文件
```

### 测试

运行测试：
```bash
python -m pytest tests/
```

### 代码检查

运行代码检查：
```bash
flake8 src/
mypy src/
```

## 发布流程

1. 更新版本号
2. 更新 CHANGELOG.md
3. 创建发布标签
4. 推送到 GitHub

## 许可证

贡献的代码将采用与项目相同的 MIT 许可证。 