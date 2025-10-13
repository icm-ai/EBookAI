const { app, BrowserWindow, dialog, shell, Menu } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const fs = require('fs')
const log = require('electron-log')

// 配置日志
log.transports.file.level = 'info'
log.transports.console.level = 'debug'

class EBookAIApp {
  constructor() {
    this.mainWindow = null
    this.backendProcess = null
    this.frontendProcess = null
    this.isDev = process.env.NODE_ENV === 'development'
    this.backendPort = 8000
    this.frontendPort = 3000

    this.setupApp()
  }

  setupApp() {
    // 设置应用事件
    app.whenReady().then(() => this.createWindow())

    app.on('window-all-closed', () => {
      this.cleanup()
      if (process.platform !== 'darwin') {
        app.quit()
      }
    })

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        this.createWindow()
      }
    })

    app.on('before-quit', () => {
      this.cleanup()
    })

    // 处理第二个实例
    const gotTheLock = app.requestSingleInstanceLock()
    if (!gotTheLock) {
      app.quit()
    } else {
      app.on('second-instance', () => {
        if (this.mainWindow) {
          if (this.mainWindow.isMinimized()) this.mainWindow.restore()
          this.mainWindow.focus()
        }
      })
    }
  }

  async createWindow() {
    log.info('Creating main window...')

    // 创建浏览器窗口
    this.mainWindow = new BrowserWindow({
      width: 1200,
      height: 800,
      minWidth: 800,
      minHeight: 600,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        enableRemoteModule: false,
        webSecurity: true
      },
      titleBarStyle: 'hiddenInset',
      show: false,
      icon: this.getAssetPath('icon.png')
    })

    // 设置应用菜单
    this.setupMenu()

    // 窗口事件
    this.mainWindow.once('ready-to-show', () => {
      this.mainWindow.show()
      if (this.isDev) {
        this.mainWindow.webContents.openDevTools()
      }
    })

    this.mainWindow.on('closed', () => {
      this.mainWindow = null
      this.cleanup()
    })

    // 处理外部链接
    this.mainWindow.webContents.setWindowOpenHandler(({ url }) => {
      shell.openExternal(url)
      return { action: 'deny' }
    })

    // 启动服务并加载应用
    await this.startServices()
  }

  async startServices() {
    try {
      log.info('Starting backend and frontend services...')

      if (this.isDev) {
        // 开发模式：连接到已运行的服务
        await this.waitForServices()
        this.mainWindow.loadURL(`http://localhost:${this.frontendPort}`)
      } else {
        // 生产模式：启动内嵌服务
        await this.startBackendService()
        await this.startFrontendService()

        // 等待服务启动
        await this.waitForServices()

        // 加载前端应用
        const frontendPath = path.join(__dirname, '../frontend/index.html')
        if (fs.existsSync(frontendPath)) {
          this.mainWindow.loadFile(frontendPath)
        } else {
          this.mainWindow.loadURL(`http://localhost:${this.frontendPort}`)
        }
      }

      log.info('Services started successfully')
    } catch (error) {
      log.error('Failed to start services:', error)
      this.showErrorDialog('启动失败', '无法启动EBookAI服务，请检查系统权限并重试。')
    }
  }

  async startBackendService() {
    return new Promise((resolve, reject) => {
      const backendPath = this.getResourcePath('backend')
      const pythonExecutable = path.join(backendPath, 'main')

      log.info('Starting backend service:', pythonExecutable)

      this.backendProcess = spawn(pythonExecutable, [], {
        cwd: backendPath,
        env: {
          ...process.env,
          PYTHONPATH: backendPath,
          PORT: this.backendPort.toString()
        }
      })

      this.backendProcess.stdout.on('data', (data) => {
        log.info('Backend stdout:', data.toString())
      })

      this.backendProcess.stderr.on('data', (data) => {
        log.warn('Backend stderr:', data.toString())
      })

      this.backendProcess.on('error', (error) => {
        log.error('Backend process error:', error)
        reject(error)
      })

      this.backendProcess.on('exit', (code) => {
        log.info('Backend process exited with code:', code)
        if (code !== 0 && code !== null) {
          reject(new Error(`Backend exited with code ${code}`))
        }
      })

      // 等待后端启动
      setTimeout(() => resolve(), 3000)
    })
  }

  async startFrontendService() {
    // 生产模式下，前端静态文件已打包，无需启动服务
    log.info('Frontend files are bundled with the application')
  }

  async waitForServices() {
    const maxRetries = 30
    const retryDelay = 1000

    // 等待后端服务
    for (let i = 0; i < maxRetries; i++) {
      try {
        const response = await fetch(`http://localhost:${this.backendPort}/health`)
        if (response.ok) {
          log.info('Backend service is ready')
          break
        }
      } catch (error) {
        if (i === maxRetries - 1) {
          throw new Error('Backend service failed to start')
        }
        await new Promise(resolve => setTimeout(resolve, retryDelay))
      }
    }

    // 开发模式下等待前端服务
    if (this.isDev) {
      for (let i = 0; i < maxRetries; i++) {
        try {
          const response = await fetch(`http://localhost:${this.frontendPort}`)
          if (response.ok) {
            log.info('Frontend service is ready')
            break
          }
        } catch (error) {
          if (i === maxRetries - 1) {
            throw new Error('Frontend service failed to start')
          }
          await new Promise(resolve => setTimeout(resolve, retryDelay))
        }
      }
    }
  }

  setupMenu() {
    const template = [
      {
        label: 'EBookAI',
        submenu: [
          {
            label: '关于 EBookAI',
            click: () => this.showAboutDialog()
          },
          { type: 'separator' },
          {
            label: '偏好设置...',
            accelerator: 'Cmd+,',
            click: () => this.showPreferences()
          },
          { type: 'separator' },
          {
            label: '隐藏 EBookAI',
            accelerator: 'Cmd+H',
            role: 'hide'
          },
          {
            label: '隐藏其他',
            accelerator: 'Cmd+Alt+H',
            role: 'hideothers'
          },
          {
            label: '显示全部',
            role: 'unhide'
          },
          { type: 'separator' },
          {
            label: '退出 EBookAI',
            accelerator: 'Cmd+Q',
            click: () => app.quit()
          }
        ]
      },
      {
        label: '文件',
        submenu: [
          {
            label: '打开文件...',
            accelerator: 'Cmd+O',
            click: () => this.openFile()
          },
          { type: 'separator' },
          {
            label: '关闭窗口',
            accelerator: 'Cmd+W',
            role: 'close'
          }
        ]
      },
      {
        label: '编辑',
        submenu: [
          { label: '撤销', accelerator: 'Cmd+Z', role: 'undo' },
          { label: '重做', accelerator: 'Shift+Cmd+Z', role: 'redo' },
          { type: 'separator' },
          { label: '剪切', accelerator: 'Cmd+X', role: 'cut' },
          { label: '复制', accelerator: 'Cmd+C', role: 'copy' },
          { label: '粘贴', accelerator: 'Cmd+V', role: 'paste' },
          { label: '全选', accelerator: 'Cmd+A', role: 'selectall' }
        ]
      },
      {
        label: '视图',
        submenu: [
          { label: '重新加载', accelerator: 'Cmd+R', role: 'reload' },
          { label: '强制重新加载', accelerator: 'Cmd+Shift+R', role: 'forceReload' },
          { label: '切换开发者工具', accelerator: 'F12', role: 'toggleDevTools' },
          { type: 'separator' },
          { label: '实际大小', accelerator: 'Cmd+0', role: 'resetZoom' },
          { label: '放大', accelerator: 'Cmd+Plus', role: 'zoomIn' },
          { label: '缩小', accelerator: 'Cmd+-', role: 'zoomOut' },
          { type: 'separator' },
          { label: '切换全屏', accelerator: 'Ctrl+Cmd+F', role: 'togglefullscreen' }
        ]
      },
      {
        label: '窗口',
        submenu: [
          { label: '最小化', accelerator: 'Cmd+M', role: 'minimize' },
          { label: '关闭', accelerator: 'Cmd+W', role: 'close' }
        ]
      },
      {
        label: '帮助',
        submenu: [
          {
            label: '学习更多',
            click: () => shell.openExternal('https://github.com/your-username/EBookAI')
          },
          {
            label: '报告问题',
            click: () => shell.openExternal('https://github.com/your-username/EBookAI/issues')
          }
        ]
      }
    ]

    const menu = Menu.buildFromTemplate(template)
    Menu.setApplicationMenu(menu)
  }

  async openFile() {
    const result = await dialog.showOpenDialog(this.mainWindow, {
      properties: ['openFile'],
      filters: [
        { name: '电子书文件', extensions: ['epub', 'pdf', 'txt', 'mobi', 'azw3'] },
        { name: '所有文件', extensions: ['*'] }
      ]
    })

    if (!result.canceled && result.filePaths.length > 0) {
      // 将文件路径发送到前端
      this.mainWindow.webContents.send('file-selected', result.filePaths[0])
    }
  }

  showAboutDialog() {
    dialog.showMessageBox(this.mainWindow, {
      type: 'info',
      title: '关于 EBookAI',
      message: 'EBookAI',
      detail: 'AI增强的电子书处理平台\n版本 1.0.0\n\n© 2024 EBookAI Team',
      buttons: ['确定']
    })
  }

  showPreferences() {
    // 打开偏好设置窗口
    this.mainWindow.webContents.send('show-preferences')
  }

  showErrorDialog(title, content) {
    dialog.showErrorBox(title, content)
  }

  getAssetPath(fileName) {
    return path.join(__dirname, '../assets', fileName)
  }

  getResourcePath(resourceName) {
    if (this.isDev) {
      return path.join(__dirname, '../../', resourceName)
    } else {
      return path.join(process.resourcesPath, resourceName)
    }
  }

  cleanup() {
    log.info('Cleaning up processes...')

    if (this.backendProcess) {
      this.backendProcess.kill('SIGTERM')
      this.backendProcess = null
    }

    if (this.frontendProcess) {
      this.frontendProcess.kill('SIGTERM')
      this.frontendProcess = null
    }
  }
}

// 启动应用
new EBookAIApp()