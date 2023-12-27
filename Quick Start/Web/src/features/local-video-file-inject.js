/**
 * mp4 音视频注入
 * 功能具体介绍：https://www.volcengine.com/docs/6394/1182637
 */

const cloudPhoneFileFolder = '/sdcard/playmp4';
const cloudPhoneFileName = 'test.mp4';

const localVideoFileInject = (vePhoneSdkInstance) => {
  let selectLocalFileInput = null;
  let uploadFileBtn = null;

  let startVideoPlayBtn = null;
  let stopVideoPlayBtn = null;

  // 把本地选择的文件传到云手机指定目录上
  const handleUploadLocalFile = (event) => {
    const localFile = event.target.files[0];

    vePhoneSdkInstance.startPushFile(localFile, {
      folder: cloudPhoneFileFolder,
      name: cloudPhoneFileName,
    });

    const handleProgress = (response) => {
      console.log('send file progress', response);
    };

    // 监听 on-send-file-progress 拿到上传文件的进度
    vePhoneSdkInstance.on('on-send-file-progress', handleProgress);

    // 监听 on-send-file-done 拿到上传文件成功的信息
    vePhoneSdkInstance.once('on-send-file-done', (response) => {
      vePhoneSdkInstance.off('on-send-file-progress', handleProgress);
      console.log('send file done response', response);
      console.log('上传本地文件成功');
    });

    // 监听 on-send-file-error 拿到上传文件失败的信息
    vePhoneSdkInstance.once('on-send-file-error', (response) => {
      vePhoneSdkInstance.off('on-send-file-progress', handleProgress);
      console.log('send file error response', response);
      console.log('上传本地文件失败');
    });
  };

  // 监听视频源状态变化
  vePhoneSdkInstance.on('on-camera-inject-status', (response) => {
    // response.status 为 2 代表视频正在播放，response.status 为 1 代表视频没有播放
    console.log('on-camera-inject-status', response);
  });

  // 返回的 startSuccess 和 stopSuccess 方法会分别在成功启动云手机和成功停止云手机时调用
  return {
    startSuccess() {
      // 触发上传本地文件的按钮
      uploadFileBtn = document.createElement('button');
      $(uploadFileBtn)
        .text('上传本地文件到云手机')
        .addClass('btn btn-primary btn-sm')
        .appendTo('.action-container')
        .on('click', () => {
          selectLocalFileInput?.click();
        });

      // 实际处理上传本地文件的 input
      selectLocalFileInput = document.createElement('input');
      $(selectLocalFileInput)
        .attr('type', 'file')
        .attr('accept', '.mp4')
        .attr('style', 'display: none')
        .appendTo('.action-container')
        .on('change', handleUploadLocalFile);

      startVideoPlayBtn = document.createElement('button');
      $(startVideoPlayBtn)
        .text('开启云手机视频注入虚拟摄像头')
        .addClass('btn btn-primary btn-sm')
        .appendTo('.action-container')
        .on('click', () => {
          // 开启之后，会收到 on-camera-inject-status 回调
          // 第一个参数代表云手机里视频的存储路径
          // 第二个参数代表播放模式, 0 代表循环播放，1 代表顺序播放
          vePhoneSdkInstance.startVideoPlay(
            `${cloudPhoneFileFolder}/${cloudPhoneFileName}`,
            0,
          );
        });

      stopVideoPlayBtn = document.createElement('button');
      $(stopVideoPlayBtn)
        .text('关闭云手机视频注入虚拟摄像头')
        .addClass('btn btn-primary btn-sm')
        .appendTo('.action-container')
        .on('click', () => {
          // 关闭之后，会收到 on-camera-inject-status 回调
          vePhoneSdkInstance.stopVideoPlay();
        });

      vePhoneSdkInstance.getVideoStatus().then((response) => {
        // response.status 为 2 代表视频正在播放，response.status 为 1 代表视频没有播放
        console.log('current video status', response);
      });
    },
    stopSuccess() {
      $(selectLocalFileInput).remove();
      selectLocalFileInput = null;

      $(uploadFileBtn).remove();
      uploadFileBtn = null;

      $(stopVideoPlayBtn).remove();
      stopVideoPlayBtn = null;

      $(startVideoPlayBtn).remove();
      startVideoPlayBtn = null;
    },
  };
};

export default localVideoFileInject;
