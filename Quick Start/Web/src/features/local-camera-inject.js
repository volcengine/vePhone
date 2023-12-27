/**
 * 本地摄像头注入
 * 功能具体介绍：https://www.volcengine.com/docs/6394/1182636
 */

// 这里映射的 MSG 仅作为告诉开发者报错 CODE 的含义
const VIDEO_CODE_MSG_MAP = {
  GET_VIDEO_TRACK_FAILED: '请授权网站获取摄像头权限', // 当申请摄像头权限被用户禁止时，code 为 'GET_VIDEO_TRACK_FAILED'
  PUBLISH_FAIL: '视频流发布失败，请重试或联系客服', // 当发布视频流失败时，code 为 ’PUBLISH_FAIL‘ ，此时可能是用户网络问题或服务异常，可以重新 start 或告知用户有异常稍后再试
};

// 这里映射的 MSG 仅作为告诉开发者报错 CODE 的含义
const AUDIO_CODE_MSG_MAP = {
  GET_AUDIO_TRACK_FAILED: '请授权网站获取麦克风权限', // 当申请麦克风权限被用户禁止时，code 为 'GET_AUDIO_TRACK_FAILED'
  PUBLISH_FAIL: '音频流发布失败，请重试或联系客服', // 当发布音频流失败时，code 为 ’PUBLISH_FAIL‘ ，此时可能是用户网络问题或服务异常，可以重新 start 或告知用户有异常稍后再试
};

const localCameraInject = (vePhoneSdkInstance) => {
  let localCameraInjectBtn = null;

  // 代表是否启用本地摄像头注入
  let enableLocalCameraInject = false;

  // 记录最后一次 remote stream start & stop 的请求，方便判断开启/关闭时是否有必要调用 stat / stop
  let latestRemoteStreamRequest = {};

  // 处理  remote-stream-start-request 事件回调
  const handleRemoteStreamStartRequest = async (res) => {
    const { isAudio, isVideo } = res;
    if (isVideo) {
      const { success, code, message } =
        await vePhoneSdkInstance.startVideoStream();

      console.log(
        'startVideoStream response, success is %s, code is %s, message is %s',
        success,
        code,
        message,
      );

      if (!success) {
        const msg =
          VIDEO_CODE_MSG_MAP[code] ||
          `本地摄像头注入失败，失败 Code：${code}，错误消息：${message}`;
        console.log(msg);
      }
    }

    if (isAudio) {
      const { success, code, message } =
        await vePhoneSdkInstance.startSendAudioStream();
      console.log(
        'startSendAudioStream response, success is %s, code is %s, message is %s',
        success,
        code,
        message,
      );
      if (!success) {
        const msg =
          AUDIO_CODE_MSG_MAP[code] ||
          `本地摄像头注入失败，失败 Code：${code}，错误消息：${message}`;
        console.log(msg);
      }
    }
  };

  // 处理 remote-stream-stop-request 事件回调
  const handleRemoteStreamStopRequest = (response) => {
    const { isAudio, isVideo } = response;
    if (isVideo) {
      vePhoneSdkInstance.stopVideoStream();
    }
    if (isAudio) {
      vePhoneSdkInstance.stopSendAudioStream;
    }
  };

  //监听云端实例请求音视频关闭回调
  vePhoneSdkInstance.on('remote-stream-start-request', (res) => {
    latestRemoteStreamRequest = { type: 'start', data: res };
    // 如果没有启用本地摄像头注入，则不处理
    if (!enableLocalCameraInject) {
      return;
    }
    handleRemoteStreamStartRequest(res);
  });

  //监听云端实例请求音视频关闭回调
  vePhoneSdkInstance.on('remote-stream-stop-request', (res) => {
    latestRemoteStreamRequest = { type: 'stop', data: res };
    // 如果没有启用本地摄像头注入，则不处理
    if (!enableLocalCameraInject) {
      return;
    }
    handleRemoteStreamStopRequest(res);
  });

  const handleLocalCameraInjectBtnClick = () => {
    if (enableLocalCameraInject) {
      // 当前是启用状态，本次需要关闭

      // 如果最新的一次回调代表云手机请求开启本地摄像头，那么在关闭本地摄像头注入时需要手动触发一次关闭
      if (latestRemoteStreamRequest.type === 'start') {
        handleRemoteStreamStopRequest(latestRemoteStreamRequest.data);
      }

      enableLocalCameraInject = false;
      $(localCameraInjectBtn).text('开启本地摄像头注入');
    } else {
      // 当前是关闭状态，本次需要启用

      // 如果最新的一次回调代表云手机请求开启本地摄像头，那么在启用本地摄像头注入时需要手动触发一次开启
      if (latestRemoteStreamRequest.type === 'start') {
        handleRemoteStreamStartRequest(latestRemoteStreamRequest.data);
      }

      enableLocalCameraInject = true;
      $(localCameraInjectBtn).text('关闭本地摄像头注入');
    }
  };

  // 返回的 startSuccess 和 stopSuccess 方法会分别在成功启动云手机和成功停止云手机时调用
  return {
    startSuccess() {
      localCameraInjectBtn = document.createElement('button');
      $(localCameraInjectBtn)
        .text('开启本地摄像头注入')
        .addClass('btn btn-primary btn-sm')
        .appendTo('.action-container')
        .on('click', handleLocalCameraInjectBtnClick);
    },
    stopSuccess() {
      $(localCameraInjectBtn).remove();
      localCameraInjectBtn = null;
    },
  };
};

export default localCameraInject;
