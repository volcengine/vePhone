# 云手机 Web SDK demo

这个开源项目展示了火山引擎云手机 Web SDK 的以下功能：

1. 启动云手机和停止云手机

方便用户快速接入云手机 Web SDK。

## 运行示例程序

1. 将 Web SDK demo 代码下载到本地；
2. 下载 Web SDK；解压后将其复制到 `lib` 文件夹下，并重命名为 `vePhoneSDK-Web.js`；
3. 在 `config.js` 中补全以下配置信息：

```js

// 实例化 vePhoneSDK 的参数
const initConfig = {
    userId: '',
    accountId: '',
    enableLocalKeyboard: true, // 是否开启本地键盘输入。前提：需要联系运营同学给云手机所在业务开启「拉起本地输入法配置」
};

// 调用 vePhoneSDK.start 的参数
// 以下只列出调用参数的必传参数，更多参数参考 Web SDK 的使用文档
const startConfig = {
  token: {
    CurrentTime: '',
    ExpiredTime: '',
    SessionToken: '',
    AccessKeyID: '',
    SecretAccessKey: ''
  },
  productId: '',
  roundId: 'vephone-demo-roundid',
  rotation: 'portrait', // landscape：横屏应用启动; portrait：竖屏应用启动
};

```

3. 在浏览器中打开 `index.html` 文件；
   
4. 点击启动云手机（开始游戏）。


