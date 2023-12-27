/**
 * 服务自动回收设置
 * 功能具体介绍：https://www.volcengine.com/docs/6394/1182638
 */

const autoRecycle = (vePhoneSdkInstance) => {
  // 返回的 startSuccess 和 stopSuccess 方法会分别在成功启动云手机和成功停止云手机时调用
  return {
    async startSuccess() {
      /**
       * 设置无操作回收时间（默认时长300秒）
       * 第一个参数为无操作回收的时长，单位为秒
       * 接口文档：https://www.volcengine.com/docs/6394/1158616#setautorecycletime
       */
      await vePhoneSdkInstance.setAutoRecycleTime(600);
      console.log('setAutoRecycleTime success');

      // 获取设置无操作回收时间
      const { duration } = await vePhoneSdkInstance.getAutoRecycleTime();
      console.log('current auto recycle duration is %s', duration);

      /**
       * 设置客户端切后台保活时间（默认时长300秒）
       * 第一个参数为切后台保活时长，单位为秒
       * 接口文档：https://www.volcengine.com/docs/6394/1158616#setidletime
       */
      await vePhoneSdkInstance.setIdleTime(100);
      console.log('setIdleTime success');
    },
  };
};

export default autoRecycle;
