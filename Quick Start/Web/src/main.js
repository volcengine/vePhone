import { startConfig, initConfig } from './config';
import { isPC, showDom, hideDom, disableBtn, activeBtn } from './utils';

const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const playerEl = document.getElementById('player');

const portraitBtn = document.getElementById('rotate-0-btn');
const landscapeBtn = document.getElementById('rotate-270-btn');

const screenshotBtn = document.getElementById('screenshot-btn');

const startScreenRecordBtn = document.getElementById('screen-record-start-btn');
const stopScreenRecordBtn = document.getElementById('screen-record-stop-btn');

// 记录是否正在录制中
let isRecording = false;

const init = () => {
  // 引入 lib 下的 火山引擎云手机 SDK 之后，会在 window 上挂一个全局变量：vePhoneSDK
  const vePhoneInstance = new window.vePhoneSDK({
    ...initConfig,
    domId: 'player', // 运行云手机的 DOM ID ，SDK 将在该 DOM 新建画布以及渲染画面
    isDebug: true,
    isPC,
    enableSyncClipBoard: true, //是否开启剪切板同步
    enableLocalKeyboard: true, //是否开启本地键盘输入功能
    enableLocalMouseScroll: true, //是否开启本地鼠标滑轮滚动映射
  });
  console.log('vePhoneSDK version', vePhoneInstance.getVersion());

  vePhoneInstance.on('message-channel-connected', (message) => {
    console.log('message-channel-connected', message);
  });

  vePhoneInstance.on('error', (error) => {
    console.log('error', error);
  });

  vePhoneInstance.on('message', (message) => {
    console.log('message', message);
  });

  vePhoneInstance.on('message-received', ({ msg }) => {
    console.log('message-received', msg);
    const { command } = msg;
    if (command === 8) {
      vePhoneInstance?.destory();
      alert('游戏超时退出');
    }
  });

  return vePhoneInstance;
};

const bindEventListener = (
  vePhoneInstance,
  startSuccessCallback,
  stopSuccessCallback
) => {
  // 启动云手机按钮绑定 click 事件，触发 vePhone SDK start
  startBtn.addEventListener('click', async () => {
    console.log('start btn click', vePhoneInstance);
    try {
      // 接口文档：https://www.volcengine.com/docs/6394/75744#%E5%90%AF%E5%8A%A8
      const startRes = await vePhoneInstance?.start(startConfig);
      console.log('start response', startRes);
      startSuccessCallback?.(vePhoneInstance);
    } catch (err) {
      console.log(err);
      alert(err.message);
    }
  });

  // 关闭云手机按钮绑定 click 事件，触发 vePhone SDK stop
  stopBtn.addEventListener('click', async () => {
    console.log('stop btn click', vePhoneInstance);
    try {
      // 接口文档：https://www.volcengine.com/docs/6394/75744#%E5%81%9C%E6%AD%A2
      const stopRes = await vePhoneInstance?.stop();
      console.log('stopRes', stopRes);
      vePhoneInstance.destroy();
      stopSuccessCallback?.(vePhoneInstance);
    } catch (err) {
      console.log(err);
      alert(err.message);
    }
  });

  // 旋转屏幕为竖屏
  portraitBtn.addEventListener('click', async () => {
    console.log('portrait btn click', vePhoneInstance);
    try {
      // 接口文档：https://www.volcengine.com/docs/6394/75744#%E5%B1%8F%E5%B9%95%E6%97%8B%E8%BD%AC
      vePhoneInstance?.rotateScreen(0, true);
      // 兼容旋转后的样式
      playerEl.classList.add('pc-portrait');
      playerEl.classList.remove('pc-landscape');
    } catch (err) {
      console.log(err);
      alert(err.message);
    }
  });

  // 旋转屏幕为横屏
  landscapeBtn.addEventListener('click', async () => {
    console.log('landscape btn click', vePhoneInstance);
    try {
      // 接口文档：https://www.volcengine.com/docs/6394/75744#%E5%B1%8F%E5%B9%95%E6%97%8B%E8%BD%AC
      vePhoneInstance?.rotateScreen(270, true);
      // 兼容旋转后的样式
      playerEl.classList.remove('pc-portrait');
      playerEl.classList.add('pc-landscape');
    } catch (err) {
      console.log(err);
      alert(err.message);
    }
  });

  // 屏幕截图
  screenshotBtn.addEventListener('click', async () => {
    console.log('screenshot btn click', vePhoneInstance);
    try {
      // 接口文档：https://www.volcengine.com/docs/6394/75744#%E4%BA%91%E6%89%8B%E6%9C%BA%E7%94%BB%E9%9D%A2%E6%88%AA%E5%9B%BE
      const screenshotRes = await vePhoneInstance?.screenShot(true);
      console.log('screenshot success', screenshotRes);
      // 在新窗口打开截图图片
      window.open(screenshotRes.downloadUrl, '_blank');
    } catch (err) {
      console.log(err);
      alert(err.message);
    }
  });

  // 开始屏幕录制
  // 注意： 这里没有处理在执行 startRecording 异步过程中，开始屏幕录制按钮可能被点击多次的逻辑
  startScreenRecordBtn.addEventListener('click', async () => {
    console.log('startScreenRecord btn click', vePhoneInstance);
    try {
      const recordTime = 120;
      // 接口文档：https://www.volcengine.com/docs/6394/75744#%E4%BA%91%E6%89%8B%E6%9C%BA%E7%94%BB%E9%9D%A2%E5%BD%95%E5%B1%8F
      await vePhoneInstance?.startRecording(recordTime, true);
      hideDom(startScreenRecordBtn);
      showDom(stopScreenRecordBtn);
      isRecording = true;
      // 支持的最大录屏时间是 14400s ,如果 14400s 之后还在录制，则处理页面元素展示逻辑
      setTimeout(() => {
        if (isRecording) {
          hideDom(stopScreenRecordBtn);
          showDom(startScreenRecordBtn);
          isRecording = false;
        }
      }, 14400 * 1000);
    } catch (err) {
      console.log(err);
      alert(err.message);
    }
  });

  // 停止屏幕录制
  // 注意： 这里没有处理在执行 stopRecording 异步过程中，停止屏幕录制按钮可能被点击多次的逻辑
  stopScreenRecordBtn.addEventListener('click', async () => {
    console.log('stopScreenRecord btn click', vePhoneInstance);
    try {
      // 接口文档：https://www.volcengine.com/docs/6394/75744#%E5%81%9C%E6%AD%A2%E7%94%BB%E9%9D%A2%E5%BD%95%E5%B1%8F
      await vePhoneInstance?.stopRecording();
      hideDom(stopScreenRecordBtn);
      showDom(startScreenRecordBtn);
      isRecording = false;
      // 由于录屏上传到对象存储可能需要较长时间，所以这里设计的是 vePhoneInstance.stopRecording 不会等待录屏上传完成之后再 resolve 
      // 所以如果想要拿到录屏视频的下载地址，我们需要在 stopRecording 之后监听 `on-screen-record-response` 事件
      // 第一次收到 `on-screen-record-response` 代表录制成功，正常结束，pod本地端保存成功
      // 第二次收到 `on-screen-record-response` 代表录制成功，上传到对象存储成功，返回下载地址
      // 下面我们只消费了录屏的下载地址，所以在手动第一个事件之后又注册了一个事件，来拿到录屏的下载地址
      vePhoneInstance.once('on-screen-record-response', () => {
        vePhoneInstance.once(
          'on-screen-record-response',
          (screenRecordResponse) => {
            // 在新窗口打开录屏视频
            window.open(screenRecordResponse.downloadUrl, '_blank');
          }
        );
      });
    } catch (err) {
      console.log(err);
      alert(err.message);
    }
  });

  // 在页面 unmount 时检查云手机是否处在运行状态，如果没有 stop ，则调用 stop
  // 这样做的好处是：1. 释放 webrtc 链接，减少浏览器内存占用 2. 释放云手机实例资源
  window.addEventListener('beforeunload', () => {
    /**
     * 这里采用 beforeunload 事件里调用 stop
     * 如果业务在 beforeunload 有业务逻辑，会调用 event.preventDefault
     * 则需要再 unload 事件里调用 stop
     */
    const connectionState = vePhoneInstance.getConnectionState();
    // connectionState 是 CONNECTED 代表云手机处在运行状态，此时我们需要 stop
    if (connectionState === 'CONNECTED') {
      vePhoneInstance?.stop();
      vePhoneInstance.destroy();
    }
  });
};

const handleStartSuccess = () => {
  hideDom(startBtn);
  showDom(stopBtn);
  activeBtn(portraitBtn);
  activeBtn(landscapeBtn);
  activeBtn(screenshotBtn);
  activeBtn(startScreenRecordBtn);
};

const handleStopSuccess = () => {
  showDom(startBtn);
  hideDom(stopBtn);
  disableBtn(portraitBtn);
  disableBtn(landscapeBtn);
  disableBtn(screenshotBtn);
  disableBtn(startScreenRecordBtn);
  hideDom(stopScreenRecordBtn);
};

// main
const vePhoneInstance = init();
bindEventListener(vePhoneInstance, handleStartSuccess, handleStopSuccess);
