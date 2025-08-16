## 🎓 ***BotClusters v7.5***

Have you encountered the problem where you have to host less resource intense Telegram Bots for free and you can only host a bot for an account but you wanted to host all bots in one instance, well say no more...

You can run multiple bots in a same instance, for now it only works for pure python bots (no docker support yet) but you need to host this on services which provide Docker support.


---

## 🔰 ***Repo Features***
- 🔄 **Auto Updates**: *Automatic updates through GitHub cloning on every restart*
- 🔌 **Extensible**: *Add unlimited bots by simply including more configuration objects*
- 🌐 **Interactive Dashboard**: *Real-time web interface for bot monitoring and control*
- 🛡️ **Reliable Process Management**:  *Powered by supervisord for automated process supervision* ***(Smart error handling and automatic recovery on failures)***
- 🔐 **Environment Control**: *Set unique ENV values for each bot*
- 🎮 **Custom Execution**: *Configure custom script paths for bot initialization*
- 🔒 **Private Repo Support**: *Clone and run bots from private repositories using tokens*
- 📦 **Custom installation**: *Custom installation of apt $ pip packages in `install.sh`*
- 🎛️ **Web Integration**: *Flask-based web application support for services like Render and Koyeb*
- 🐍 **Multi-Python Support**: *Supports multiple python version for each bot config*
  
---

## 🚀 ***Quick Start***
* **Fork and Star this repository**
* **Deploy to your preferred platform using the buttons below**
* **Configure your bots in the clusters configuration**
  
---

## #️⃣ Sample `Var.CLUSTERS`

| Config | Description | Required(compulsory) |
|----------|-------------|----------|
| `botname` | Unique name for your bot | ✅ |
| `git_url` | GitHub repository URL | ✅ |
| `branch` | Repository branch name | ✅ |
| `run_command` | Bot execution command | ✅ |
| `env` | Environment variables | ❌ |
| `python_version` | Python Version | ❌ |

---

## ✅ Supported Python Versions

`python3.8`
`python3.9`
`python3.10`
`python3.11`
`python3.12`
`python3.13`

---

## 🛠️ ***Setup Guide***

* **Args:**
```
["botname", "git_url", "branch", "run_command", "env"]
```

* **For Public Repositories:**
```
["bot01", "https://github.com/mysterydemon/botcluster.git", "main", "bot.py", {"PORT": "8787"}]
```

* **For Private Repositories:**
```
["bot01", "https://mysterydemon:<your_github_private_token>@github.com/MysteryDemon/botcluster.git", "main", "main.py", {"PORT": "6060"}]
```

* **For Custom Python Version:**
```
["bot01", "https://mysterydemon:<your_github_private_token>@github.com/MysteryDemon/botcluster.git", "main", "main.py", {"PORT": "6060"}, "3.9"]
```
  
---

## 📤 ***How To Deploy***
[![Watch Tutorial](https://img.shields.io/badge/Watch%20Tutorial-%23FF0000?style=for-the-badge&logo=YouTube&logoColor=white)](https://youtu.be/saXUJEMJZJ0?si=K01v671F1xVhtePq)

---

## ⚡ ***Deploy***
[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://dashboard.heroku.com/new?template=https://github.com/MysteryDemon/BotClusters)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/MysteryDemon/BotClusters)

[![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?type=git&builder=dockerfile&repository=github.com/mysterydemon/BotClusters&branch=main&name=botclusters&ports=5000;http;/&env[CLUSTER_01]=)

---

## 📝 ***Notes***
* **Ensure all your bots are compatible with Python**
* **Its not compulsory to set a python version only use when your bot needs a specific python version to run on**
* **Docker support is in development**
* **Keep your tokens and sensitive information secure**
* **if your Bot has a dependency of packages thats not installed yet, use `install.sh` to install them**
* **For FFMPEG Support use the [`master`](https://github.com/MysteryDemon/BotClusters/tree/master) branch**
* **[GUI](https://i.ibb.co/k2TBk6wR/IMG-20250524-213433-914-edit-261278564505495.png) login details:**

`Username`
```
admin
```
`Password`
```
password123
```

---

## 🤝 ***Contributing***
* **Contributions are welcome! Please feel free to submit a Pull Request.**
  
---

### 📚 ***References***

- `Source Repository` : [MultiBots](https://github.com/bipinkrish/MultiBots)

