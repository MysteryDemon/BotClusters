<div align="center">
    <a href="https://github.com/MysteryDemon/BotClusters">
        <kbd>
            <img width="2000" src="https://te.legra.ph/file/337898fcd33f27b9de71d.jpg" alt="Bot Clusters Logo">
        </kbd>
    </a>
</div>

---

## 📖 ***BotClusters***

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
  
---

## 🚀 ***Quick Start***
* **Fork and Star this repository**
* **Deploy to your preferred platform using the buttons below**
* **Configure your bots in the clusters configuration**
  
---

## #️⃣ Sample `Var.CLUSTERS`

| Config | Description | Required |
|----------|-------------|----------|
| `botname` | Unique name for your bot | ✅ |
| `git_url` | GitHub repository URL | ✅ |
| `branch` | Repository branch name | ✅ |
| `run_command` | Bot execution command | ✅ |
| `env` | Environment variables | ❌ |

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
  
---

## 📤 ***How To Deploy***
[![Watch Tutorial](https://img.shields.io/badge/Watch%20Tutorial-%23FF0000?style=for-the-badge&logo=YouTube&logoColor=white)](https://youtu.be/EZJSQVtEj9o)

---

## ⚡ ***Deploy***
[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://dashboard.heroku.com/new?template=https://github.com/MysteryDemon/BotClusters)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/MysteryDemon/BotClusters)

[![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?type=git&builder=dockerfile&repository=github.com/mysterydemon/BotClusters&branch=main&name=botclusters&ports=5000;http;/&env[CLUSTER_01]=)

---

## 📝 ***Notes***
* **Ensure all your bots are compatible with Python**
* **Docker support is in development**
* **Keep your tokens and sensitive information secure**
* **if your Bot has a dependency of packages thats not installed yet, use `install.sh` to install them**
* **For FFMPEG Support add `ffmpeg` to the apt packages in `install.sh`**
* **GUI login details:**

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
