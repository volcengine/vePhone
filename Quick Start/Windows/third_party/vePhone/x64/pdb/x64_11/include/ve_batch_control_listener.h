#pragma once
#include "ve_type_defines.h"


namespace vecommon {

/**
 * @locale zh
 * @type callback
 * @brief 批量拉流监听器类
 */
class BatchControlListener {

public:

    /**
     * @locale zh
     * @brief 请求BatchPodStart完成的回调
     * @param code 状态码
     * @param msg 详细信息
     * @param podInfoList 成功推流的云机列表
     * @param podErrorList 有问题的云机列表
     * @note 请求完成后，可以调用{@link BatchControlVideo#start()来开始批量拉流操作}
     */
    virtual void onBatchPodStartResult(int code, const char* msg, const std::vector<vecommon::PodInfo>* podInfoList, 
        const std::vector<vecommon::PodError>* podErrorList) {}

    /**
     * @locale zh
     * @brief 开始批量拉流成功的回调
     * @param podId 云机ID
     */
    virtual void onStartSuccess(const char* podId) {}

    /**
     * @locale zh
     * @brief 云机加房回调
     * @param podId 云机ID
     */
    virtual void onPodJoin(const char* podId) {
        (void)podId;
    }

    /**
     * @locale zh
     * @brief 收到首帧视频流的回调
     * @param podId 云机ID
     * @param profileId 清晰度ID
     */
    virtual void onFirstVideoFrameArrived(const char* podId, int profileId) {
        (void)podId;
        (void)profileId;
    }

    /**
     * @locale zh
     * @brief 视频流停止的回调
     * @param podId 云机ID
     */
    virtual void onStop(const char* podId) {
        (void)podId;
    }

    /**
     * @locale zh
     * @brief 错误回调
     * @param podId 云机ID
     * @param code 错误码
     * @param msg 错误信息
     */
    virtual void onError(const char* podId, int code, const char* msg) {
        (void)podId;
        (void)code;
        (void)msg;
    }

    /**
     * @locale zh
     * @brief 警告回调
     * @param podId 云机ID
     * @param code 警告码
     * @param msg 警告信息
     */
    virtual void onWarning(const char* podId, int code, const char* msg) {
        (void)podId;
        (void)code;
    }

};

} // namespace vecommon