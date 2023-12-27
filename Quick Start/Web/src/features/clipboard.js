/**
 * 剪贴板相关功能
 * 相关初始化参数 enableSyncClipboard
 * 功能具体介绍：https://www.volcengine.com/docs/6394/1182634
 */

const clipboard = (vePhoneSdkInstance) => {
  let syncBtn = null;
  let clipboardDataDropdown = null;

  // 把本地剪贴板的文本同步到云手机剪贴板中
  const syncLocalClipboardToCloudPhoneClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText();
      console.log('local clipboard text is %s', text);
      vePhoneSdkInstance.sendClipBoardMessage(text);
    } catch (err) {
      console.log('syncLocalClipboardToCloudPhoneClipboard error', err);
    }
  };

  // 处理 clipboard-message-received 事件，把云手机上的剪贴板展示到页面上
  const handleClipboardMessageReceived = (response) => {
    const li = document.createElement('li');
    $(li)
      .addClass('dropdown-item')
      .text(decodeURIComponent(response[0]))
      .prependTo($(clipboardDataDropdown).find('.clipboard-list'));
  };

  /**
   * 监听云手机实例剪贴板发生变化时的回调
   * 回调的入参是一个字符串数组
   * 接口文档：https://www.volcengine.com/docs/6394/1158618#clipboard-message-received
   */
  vePhoneSdkInstance.on(
    'clipboard-message-received',
    handleClipboardMessageReceived,
  );

  // 返回的 startSuccess 和 stopSuccess 方法会分别在成功启动云手机和成功停止云手机时调用
  return {
    startSuccess() {
      // 剪贴板数据展示的 dom 节点
      clipboardDataDropdown = document.createElement('div');
      $(clipboardDataDropdown)
        .addClass('dropdown')
        .html(
          `<button class="btn btn-sm btn-primary dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">云手机剪贴板数据</button><ul class="dropdown-menu clipboard-list"></ul>`,
        )
        .appendTo('.action-container');

      // 手动同步本地剪贴板到云手机按钮
      syncBtn = document.createElement('button');
      $(syncBtn)
        .text('同步本地剪贴板到云手机')
        .addClass('btn btn-primary btn-sm')
        .appendTo('.action-container')
        .on('click', syncLocalClipboardToCloudPhoneClipboard);
    },
    stopSuccess() {
      $(syncBtn).remove();
      syncBtn = null;

      $(clipboardDataDropdown).remove();
      clipboardDataDropdown = null;
    },
  };
};

export default clipboard;
