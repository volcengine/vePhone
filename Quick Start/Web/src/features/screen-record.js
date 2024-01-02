/**
 * 屏幕录制功能
 */

const screenRecord = (vePhoneSdkInstance) => {
  // 记录是否正在录制中
  let isRecording = false;

  let startScreenRecordBtn = null;
  let stopScreenRecordBtn = null;

  let timeoutId = null;

  // 开始屏幕录制
  const handleStartRecording = async () => {
    console.log('startScreenRecord btn click');
    // 如果已经开始了屏幕录制，不再处理
    // startRecording 是一个异步过程，实际业务中可以给开始屏幕录制按钮添加一个 loading 态，提高用户体验
    if (isRecording) {
      return;
    }
    // 再次开始录屏之前，清除上次的定时器
    clearTimeout(timeoutId);
    try {
      isRecording = true;
      const maxDuration = 1 * 60 * 60; // 单位为秒，录屏时长最大为 4 小时，这里配置录屏时长为 1 小时，支持用户手动停止录屏
      /**
       * sdk.startRecording 会录制当前云手机的画面并上传到对象存储，会返回一个视频的下载链接
       * 第一个参数代表录屏的时长，达到录屏时长后，会自动停止，同时会收到 on-screen-record-response 回调，回调 status 是 6
       * 第二个参数的的含义是「是否将截图保存到云手机本地」，默认为不保存
       * 更多细节以及注意事项请查阅接口文档：https://www.volcengine.com/docs/6394/75744#%E4%BA%91%E6%89%8B%E6%9C%BA%E7%94%BB%E9%9D%A2%E5%BD%95%E5%B1%8F
       */
      await vePhoneSdkInstance?.startRecording(maxDuration + 60, true); // 这里在 maxDuration 基础上加 60s 是为了由业务自己手动控制停止的逻辑，否则就需要在回调里处理页面状态

      // 隐藏开始录制按钮，展示停止录制按钮
      $(startScreenRecordBtn).hide();
      $(stopScreenRecordBtn).show();

      // 如果达到最大的录屏时间
      timeoutId = setTimeout(() => {
        if (isRecording) {
          handleStopRecording();
        }
      }, maxDuration * 1000);
    } catch (err) {
      // 开启失败时，回滚 isRecording 状态
      isRecording = false;
      console.log(err);
      console.log(err.message);
    }
  };

  // 停止屏幕录制
  const handleStopRecording = async () => {
    console.log('stopScreenRecord btn click');
    // 如果已经停止了屏幕录制，不再处理
    // stopRecording 是一个异步过程，实际业务中可以给停止屏幕录制按钮添加一个 loading 态，提高用户体验
    if (!isRecording) {
      return;
    }
    // 结束录屏之前，清除定时器，避免意外多次调用 handleStopRecording
    clearTimeout(timeoutId);
    try {
      isRecording = false;
      // 接口文档：https://www.volcengine.com/docs/6394/75744#%E5%81%9C%E6%AD%A2%E7%94%BB%E9%9D%A2%E5%BD%95%E5%B1%8F
      await vePhoneSdkInstance?.stopRecording();

      // 展示开始录制按钮，隐藏停止录制按钮
      $(startScreenRecordBtn).show();
      $(stopScreenRecordBtn).hide();

      // 由于录屏上传到对象存储可能需要较长时间，所以这里设计的是 vePhoneSdkInstance.stopRecording 不会等待录屏上传完成之后再 resolve
      // 所以如果想要拿到本次录屏的下载地址，需要在 stopRecording 之后监听 `on-screen-record-response` 事件
      // 第一次收到 `on-screen-record-response` 代表录制成功，正常结束
      // 第二次收到 `on-screen-record-response` 代表录制成功，上传到对象存储成功，返回下载地址
      // 下面我们只消费了录屏的下载地址，所以在手动第一个事件之后又注册了一个事件，来拿到录屏的下载地址
      vePhoneSdkInstance.once('on-screen-record-response', ({ status }) => {
        // 第一次回调应该为 1，代表录制正常结束
        if (status !== 1) {
          console.log(`录屏失败，失败状态为${status}`);
          return;
        }
        // 第一次回调是 1 时，再次监听事件回调，拿到录制文件的 url 地址
        vePhoneSdkInstance.once(
          'on-screen-record-response',
          (screenRecordResponse) => {
            console.log('screen record success', screenRecordResponse);
            /**
             * status 取值
             * 0（录制成功，正常结束，上传 TOS 成功）
             * 1（录制成功，正常结束）
             * 2（开始录制成功）
             * 3（开始录制失败，正在录制中时调用了开始录制）
             * 4（结束录制失败，没有录制中的任务）
             * 5（录制失败，云手机存储空间不足，已占用存储空间总量的 80%）
             * 6（录制结束，达到录制时限）
             * 7（开始录制失败，录制时长超过上限）
             * 8（未知错误）
             */
            if (screenRecordResponse.status !== 0) {
              console.log(`录屏失败，失败状态为${status}`);
              return;
            }
            // screenRecordResponse.downloadUrl 是一个类似「https://screencap.tos-cn-shanghai.volces.com/xxx.jpg」的 URL，跟实际业务所在的域名是不同的源(origin)
            // 在新窗口打开录屏视频
            window.open(screenRecordResponse.downloadUrl, '_blank');
          },
        );
      });
    } catch (err) {
      // 停止失败时，回滚 isRecording 状态
      isRecording = true;
      console.log(err);
      console.log(err.message);
    }
  };

  // 这里主要处理 demo 应用的一些逻辑，主要关注上方录制和停止录制的逻辑
  // 返回的 startSuccess 和 stopSuccess 方法会分别在成功启动云手机和成功停止云手机时调用
  return {
    startSuccess() {
      // 创建开始录制按钮并将其添加到页面操作按钮容器中
      startScreenRecordBtn = document.createElement('button');
      $(startScreenRecordBtn)
        .text('开始录制')
        .addClass('btn btn-primary btn-sm')
        .appendTo('.action-container')
        .on('click', handleStartRecording);

      // 创建停止录制按钮并将其添加到页面操作按钮容器中，停止录制按钮默认是隐藏的。当开启录制之后才展示
      stopScreenRecordBtn = document.createElement('button');
      $(stopScreenRecordBtn)
        .text('停止录制')
        .addClass('btn btn-primary btn-sm')
        .appendTo('.action-container')
        .hide()
        .on('click', handleStopRecording);
    },
    stopSuccess() {
      $(startScreenRecordBtn).remove();
      $(stopScreenRecordBtn).remove();
      startScreenRecordBtn = null;
      stopScreenRecordBtn = null;
    },
  };
};

export default screenRecord;
