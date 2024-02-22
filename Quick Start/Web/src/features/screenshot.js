/**
 * 截图功能
 */

const screenshot = (vePhoneSdkInstance) => {
  let screenshotBtn = null;

  // 点击截图按钮的回调
  const handleScreenshot = async () => {
    console.log('screenshot btn click', vePhoneSdkInstance);
    try {
      /**
       * sdk.screenShot 会截取当前云手机的画面并上传到对象存储，会返回一个图片的下载链接
       * 第一个参数的的含义是「是否将截图保存到云手机本地」，true 代表保存到云手机本地，false 代表不保存，必填
       * 更多细节以及注意事项请查阅接口文档：https://www.volcengine.com/docs/6394/75744#%E4%BA%91%E6%89%8B%E6%9C%BA%E7%94%BB%E9%9D%A2%E6%88%AA%E5%9B%BE
       */
      const screenshotRes = await vePhoneSdkInstance?.screenShot(true);
      console.log('screenshot success', screenshotRes);
      const { result, message } = screenshotRes;
      /**
       * result 取值
       * 0：截图成功
       * -1：存储空间不足，截图失败;
       * -2：未知原因，截图失败
       */
      if (result !== 0) {
        console.log(`截图失败：${message}`);
        return;
      }
      // screenshotRes.downloadUrl 是一个类似「https://screencap.tos-cn-shanghai.volces.com/xxx.jpg」的 URL，跟实际业务所在的域名是不同的源(origin)
      // 在新窗口打开截图图片
      window.open(screenshotRes.downloadUrl, '_blank');
    } catch (err) {
      console.log(err);
      console.log(err.message);
    }
  };

  // 这里主要处理 demo 应用的一些逻辑，主要关注上方点击截图按钮回调之后的处理逻辑即可
  // 返回的 startSuccess 和 stopSuccess 方法会分别在成功启动云手机和成功停止云手机时调用
  return {
    startSuccess() {
      // 创建截图操作按钮并将其添加到页面操作按钮容器中
      screenshotBtn = document.createElement('button');
      $(screenshotBtn)
        .text('截图')
        .addClass('btn btn-primary btn-sm')
        .appendTo('.action-container')
        .on('click', handleScreenshot);
    },
    stopSuccess() {
      $(screenshotBtn).remove();

      screenshotBtn = null;
    },
  };
};

export default screenshot;
