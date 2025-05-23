# 云手机 WebSDK Quick Start

本项目是火山引擎云手机 Web SDK 的 Quick Start Example，借助 Web SDK 实现了以下功能，方便用户快速接入云手机 Web SDK。

1. 启动云手机和停止云手机
2. 旋转屏幕
3. 屏幕截图
4. 屏幕录制
5. 服务回收设置
6. 剪贴板同步
7. 摄像头注入
8. 操控权限配置等

> 注意：本项目中有较多链接会跳转到云手机火山引擎文档中心，如果跳转到火山引擎文档中心没有显示 SDK 下载链接或 SDK 接口文档，需要先使用已经开通云手机服务的账号登录火山引擎官网

## 目录结构

```js
src
├── config.js // 导出 Web SDK 需要的配置
├── index.html // 页面布局
├── libs // Web SDK 资源包所在的目录
├── features // Web SDK 的一些功能代码片段
├── .env // Web SDK 启动需要的配置
├── main.js // 主要的实现逻辑
└── utils.js // 工具函数
```

## 运行示例程序

> 首先需要确保拥有 `node` 环境，如果没有，请前往 [nodejs 官网](https://nodejs.org/zh-cn/download)下载并安装 `nodejs`

1. 下载项目到本地

```bash
git clone https://github.com/volcengine/vePhone.git
```

2. 进入 Web Quick Start 目录

```bash
cd vePhone/Quick Start/Web
```

3. 前往[云手机火山官网文档中心](!https://www.volcengine.com/docs/6394/1274174)下载 sdk 最新版本，将 sdk 文件重命名为 `vephone-sdk.min.js` 放到 `src/libs` 目录下。
注：如果点击上面链接没有看到下载 sdk 文件的位置，请确保登录火山账号，且账号已经加白云手机


4. 安装依赖

```bash
npm install
```

5. 在 src 目录的`.env`文件，填写启动云手机需要的配置，配置如下：

```bash
# init config
VEPHONE_ACCOUNT_ID="your accountId" # 火山引擎用户账号，可通过火山引擎官网页面右上角 用户 > 账号管理 > 主账号信息 获取

# start config
VEPHONE_PRODUCT_ID="your productId" # 云手机业务 ID，可通过火山引擎云手机控制台『业务管理』页面获取
VEPHONE_POD_ID="your podId" # 实例 ID，可通过火山引擎云手机控制台『实例管理』页面获取

# start token 启动云手机的令牌（通过调用服务端 STSToken 接口获取），有关服务端 STSToken 接口的详细信息，参考 [签发临时 Token](https://www.volcengine.com/docs/6394/75752)
 # Token 创建时间
VEPHONE_TOKEN_CURRENT_TIME=""
 #Token 过期时间
VEPHONE_TOKEN_EXPIRED_TIME=""
# 用于鉴权的临时 Token
VEPHONE_TOKEN_SESSION_TOKEN=""
# 用于鉴权的临时 Access Key
VEPHONE_TOKEN_ACCESS_KEY_ID=""
# 用于鉴权的临时 Secret Key
VEPHONE_TOKEN_SECRET_ACCESS_KEY=""

```

6. 执行启动命令

```bash
npm run dev
```

7. 打开浏览器，访问 `localhost:8080` 即可

