# 本地测试命令

```powershell
cd ai-compliance-workbench\backend
python -m pip install -r requirements.txt
python -m pytest -q

cd ..\frontend
npm install
npm run build
```

完整运行：

```powershell
cd ai-compliance-workbench
.\scripts\start_dev.ps1
```
