import { startConfig, initConfig } from './config';
import * as features from './features';
import { isPC } from './utils.js';

console.log('jquery version is %s', $.fn.jquery);

// 初始化 Demo ，跟 SDK 逻辑无关
const initApp = () => {
  if (isPC) {
    $('#player').addClass('pc-player pc-portrait');
  }

  $('#show-action-btn').draggable({ containment: document.body });

  $('#hide-action-btn').on('click', () => {
    $('.action-container').hide();
    $('#show-action-btn').show();
  });

  $('#show-action-btn').on('click', () => {
    $('.action-container').show();
    $('#show-action-btn').hide();
  });
};

const initSdk = () => {
  // 引入 lib 下的 火山引擎云手机 SDK 之后，会在 window 上挂一个全局变量：vePhoneSDK
  const vePhoneSdkInstance = new window.vePhoneSDK({
    ...initConfig,
    domId: 'player', // 运行云手机的 DOM ID ，SDK 将在该 DOM 新建画布以及渲染画面
    isDebug: import.meta.env.DEV, // 本地调试开启 debug 模式，线上关闭
    enableLocalKeyboard: false,
    enableSyncClipboard: true, //是否开启剪切板同步，相关 API 参考 features/clipboard.js。详细参考剪贴板同步最佳实践（https://www.volcengine.com/docs/6394/1182634）
    enableLocalMouseScroll: true, //是否开启本地鼠标滑轮滚动映射
  });
  console.log('vePhoneSDK version', vePhoneSdkInstance.getVersion());

  vePhoneSdkInstance.on('message-received', ({ msg }) => {
    const { command } = msg;
    if (command === 8) {
      console.log('游戏超时退出');
    }
  });

  // 调试用，线上环境请删除
  if (import.meta.env.DEV) {
    window.vePhoneSdkInstance = vePhoneSdkInstance;
  }

  return vePhoneSdkInstance;
};

const bindMainEventListener = (vePhoneSdkInstance, callback) => {
  let isStart = false;
  const handleStart = async () => {
    console.log('start btn click');
    // 如果已经调用过 start，不再处理
    // sdk.start 是一个异步过程，实际业务中可以给启动云手机按钮添加一个 loading 态，提高用户体验
    if (isStart) {
      return;
    }
    console.log('starting');
    try {
      isStart = true;
      // 接口文档：https://www.volcengine.com/docs/6394/75744#%E5%90%AF%E5%8A%A8
      const startRes = await vePhoneSdkInstance?.start({
        ...startConfig,
        rotation: 'portrait', // 以竖屏状态启动，具体详见：https://www.volcengine.com/docs/6394/1182635
        isScreenLock: !isPC, // 移动端是开启锁定屏幕横竖屏显示（即默认开启自动旋转功能，移动端时监听 orientation 进行画面旋转）具体详见：https://www.volcengine.com/docs/6394/1182635
        mute: true,
        audioAutoPlay: true, // mute & audioAutoPlay 都配置 true 是处理自动播放的策略，这里配置为 **初始化静音，用户首次点击时开启声音**，详细配置及原因详见自动播放最佳实践（https://www.volcengine.com/docs/6394/154997）
      });
      console.log('start success', startRes);

      // 隐藏启动云手机按钮， 展示关闭云手机按钮
      $('#start-btn').hide();
      $('#stop-btn').show();

      callback?.startSuccess?.();
    } catch (err) {
      // 启动失败时，回滚状态
      isStart = false;
      console.error('start error', err);
    }
  };

  const handleStop = async () => {
    console.log('stop btn click');
    // 如果没有启动，不处理
    // sdk.stop 是一个异步过程，实际业务中可以给关闭云手机按钮添加一个 loading 态，提高用户体验
    if (!isStart) {
      return;
    }
    console.log('stopping');
    try {
      isStart = false;
      // 接口文档：https://www.volcengine.com/docs/6394/75744#%E5%81%9C%E6%AD%A2
      const stopRes = await vePhoneSdkInstance?.stop();
      console.log('stop success', stopRes);

      // 展示启动云手机按钮， 隐藏关闭云手机按钮
      $('#start-btn').show();
      $('#stop-btn').hide();

      callback?.stopSuccess?.();
    } catch (err) {
      // 关闭失败时，回滚状态
      isStart = true;
      console.log(err);
    }
  };

  $('#start-btn').on('click', handleStart);
  $('#stop-btn').on('click', handleStop);

  // 在页面 unmount 时检查云手机是否处在运行状态，如果没有 stop ，则调用 stop
  // 这样做的好处是：1. 释放 webrtc 链接，减少浏览器内存占用 2. 释放云手机实例资源
  window.addEventListener('beforeunload', () => {
    /**
     * 这里采用 beforeunload 事件里调用 stop
     * 如果业务在 beforeunload 有业务逻辑，会调用 event.preventDefault
     * 则需要再 unload 事件里调用 stop
     */
    const connectionState = vePhoneSdkInstance.getConnectionState();
    // connectionState 是 CONNECTED 代表云手机处在运行状态，此时我们需要 stop
    if (connectionState === 'CONNECTED') {
      vePhoneSdkInstance?.stop();
      vePhoneSdkInstance.destroy();
    }
  });
};

const initFeatures = (vePhoneSdkInstance) => {
  const startSuccessCallbackList = [];
  const stopSuccessCallbackList = [];

  Object.keys(features)
    .map((featName) => features[featName](vePhoneSdkInstance))
    .forEach((result) => {
      if (result?.startSuccess) {
        startSuccessCallbackList.push(result?.startSuccess);
      }
      if (result?.stopSuccess) {
        stopSuccessCallbackList.push(result?.stopSuccess);
      }
    });

  return {
    startSuccess() {
      for (const fn of startSuccessCallbackList) {
        try {
          fn();
        } catch (err) {
          console.error('execute startSuccess callback error', err);
        }
      }
    },
    stopSuccess() {
      for (const fn of stopSuccessCallbackList) {
        try {
          fn();
        } catch (err) {
          console.error('execute stopSuccess callback error', err);
        }
      }
    },
  };
};

(async () => {
  // 在启动云手机之前，先检测用户的浏览器是否支持 rtc， 如果不支持，提示用户更换浏览器
  const isSupportRtc = await window.vePhoneSDK.isRtcSupported();
  if (!isSupportRtc) {
    console.log('当前浏览器不支持 WebRTC，请更换浏览器');
    return;
  }
  initApp();
  const vePhoneSdkInstance = initSdk();
  const callback = initFeatures(vePhoneSdkInstance);
  bindMainEventListener(vePhoneSdkInstance, callback);
})();
