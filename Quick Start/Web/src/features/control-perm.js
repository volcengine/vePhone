/**
 * 操控权限配置功能
 * 具体介绍详见：https://www.volcengine.com/docs/6394/1182642
 */

const controlPerm = (vePhoneSdkInstance) => {
  let disableControlBtn = null;
  let enableControlBtn = null;

  // 查询当前用户的操控权限
  const getCurrenUserControlPermission = async () => {
    // vePhoneSdkInstance.hasControl 的 promise 只会 resolve，不会 reject
    // 正常情况 code 为 0 ，否则 code 小于 0
    // data 是一个对象，结构是 {enable: boolean, userId: string}
    const { code, msg, data } = await vePhoneSdkInstance.hasControl(
      vePhoneSdkInstance.userId,
    );
    if (code !== 0) {
      console.log('hasControl error', msg);
      return;
    }
    if (data.enable) {
      console.log('当前用户有操控权限');
    } else {
      console.log('当前用户没有操控权限');
    }
  };

  // 查询当前房间内所有用户的操控权限
  const getAllControls = async () => {
    // vePhoneSdkInstance.getAllControls 的 promise 只会 resolve，不会 reject
    // 正常情况 code 为 0 ，否则 code 小于 0
    const { code, msg, data } = await vePhoneSdkInstance.getAllControls();
    if (code !== 0) {
      console.log('getAllControls error', msg);
      return;
    }
    // data 是一个对象数组，对象结构是 {enable: boolean, userId: string}
    console.log('getAllControls data', data);

    console.log(
      `当前房间一共有 ${data.length} 人，其中有权限的共 ${
        data.filter((item) => item.enable).length
      } 人`,
    );
  };

  const handleDisableControlBtnClick = async (enable) => {
    // 接口文档：https://www.volcengine.com/docs/6394/1158616#enablecontrol
    const { code, msg, data } = await vePhoneSdkInstance.enableControl(
      vePhoneSdkInstance.userId,
      enable,
    );
    if (code !== 0) {
      console.log('设置当前用户操控权限失败', msg);
      return;
    }
    console.log(`设置当前用户操控权限成功，当前用户操控权限为：${enable}`);
  };

  // 返回的 startSuccess 和 stopSuccess 方法会分别在成功启动云手机和成功停止云手机时调用
  return {
    startSuccess() {
      getCurrenUserControlPermission();
      getAllControls();

      disableControlBtn = document.createElement('button');
      $(disableControlBtn)
        .text('禁止当前用户操控')
        .addClass('btn btn-primary btn-sm')
        .appendTo('.action-container')
        .on('click', () => handleDisableControlBtnClick(false));

      enableControlBtn = document.createElement('button');
      $(enableControlBtn)
        .text('允许当前用户操控')
        .addClass('btn btn-primary btn-sm')
        .appendTo('.action-container')
        .on('click', () => handleDisableControlBtnClick(true));
    },
    stopSuccess() {
      $(enableControlBtn).remove();
      enableControlBtn = null;

      $(disableControlBtn).remove();
      disableControlBtn = null;
    },
  };
};

export default controlPerm;
