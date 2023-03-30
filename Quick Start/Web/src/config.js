// 初始化配置由环境变量中获得
// 由于采用的是 vite 构建的，所以环境变量在 import.meta.env 中。详见 https://cn.vitejs.dev/guide/env-and-mode.html
export const initConfig = {
  userId: 'vephone-github-web-quick-start', // 自定义客户端用户 ID，用于区分用户
  accountId: import.meta.env.VEPHONE_ACCOUNT_ID, // 火山引擎用户账号，可通过火山引擎官网页面右上角 用户 > 账号管理 > 主账号信息 获取
};


// start 配置由环境变量中获得
// 由于采用的是 vite 构建的，所以环境变量在 import.meta.env 中。详见 https://cn.vitejs.dev/guide/env-and-mode.html
export const startConfig = {
  useCloudNative: true,
  productId: import.meta.env.VEPHONE_PRODUCT_ID,
  podId: import.meta.env.VEPHONE_POD_ID,
  token: {
    AccessKeyID: import.meta.env.VEPHONE_TOKEN_ACCESS_KEY_ID,
    SecretAccessKey: import.meta.env.VEPHONE_TOKEN_SECRET_ACCESS_KEY,
    SessionToken: import.meta.env.VEPHONE_TOKEN_SESSION_TOKEN,
    CurrentTime: import.meta.env.VEPHONE_TOKEN_CURRENT_TIME,
    ExpiredTime: import.meta.env.VEPHONE_TOKEN_EXPIRED_TIME,
  }
};

console.log('env', import.meta.env)

if (!import.meta.env.VEPHONE_TOKEN_SESSION_TOKEN) {
  console.error("请参考 README 中补充运行需要的环境变量")
}