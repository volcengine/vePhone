/**
 * 画面旋转功能
 * 具体详见：https://www.volcengine.com/docs/6394/1182635
 */

const rotation = (vePhoneSdkInstance) => {
  //回调监听（各旋转角度对应的返回值，用于监听当前画面状态）
  vePhoneSdkInstance.on('on-screen-rotation', (data) => {
    console.log('on screen rotation', data);
  });

  let portraitScreenBtn = null;

  let landscapeScreenBtn = null;

  // 返回的 startSuccess 和 stopSuccess 方法会分别在成功启动云手机和成功停止云手机时调用
  return {
    startSuccess() {
      // demo 的 pc 场景才展示横竖屏切换按钮
      if (vePhoneSdkInstance.isPC) {
        portraitScreenBtn = document.createElement('btn');
        $(portraitScreenBtn)
          .text('竖屏')
          .addClass('btn btn-primary btn-sm')
          .appendTo('.action-container')
          .on('click', () => {
            $('#player').removeClass('pc-landscape').addClass('pc-portrait');
            // 调用 rotateScreen 旋转屏幕为竖屏
            // 第一个参数代表旋转角度，第二个参数代表是否 pod 跟着一起旋转
            vePhoneSdkInstance.rotateScreen(0, false);
          });

        landscapeScreenBtn = document.createElement('btn');
        $(landscapeScreenBtn)
          .text('横屏')
          .addClass('btn btn-primary btn-sm')
          .appendTo('.action-container')
          .on('click', () => {
            $('#player').removeClass('pc-portrait').addClass('pc-landscape');
            // 调用 rotateScreen 旋转屏幕为横屏
            // 第一个参数代表旋转角度（逆时针），第二个参数代表是否 pod 跟着一起旋转
            vePhoneSdkInstance.rotateScreen(90, false);
          });
      }
    },
    stopSuccess() {},
  };
};

export default rotation;
