#pragma once
#include "ve_type_defines.h"

class BatchControlListener
{
public:

    /**
     * @type callback
     * @brief BatchPodStart�ɹ�
     * @param [in] code, ״̬��  <br>
     * @param [in] msg, ������Ϣ  <br>
     */
    virtual void onBatchPodStartResult(int code, const char* msg, const std::vector<vecommon::PodInfo>* pod_list, const std::vector<vecommon::PodError>* pod_errors) {
        // 1. ����ɹ�������bcv.start�ӿ�
    }

    /**
     * @type callback
     * @brief start�ɹ��ص�
     */
    virtual void onStartSuccess(const char* pod_id) {
    }

    /**
     * @type callback
     * @brief Զ���û��ӷ��ص�
     *        - ���ݶ�Ӧ��pod�����Ƿ���û��ɼ����������Ƿ���ж��Ĳ���
     *        - Warning: ���ܻ�������֡��ʱ
     * @param [in] pod_id���Զ�podId  <br>
     */
    virtual void onPodJoin(const char* pod_id) {
        (void)pod_id;
    }

    /**
     * @type callback
     * @brief �����ɹ�
     * @param [in] pod_id, �Զ�podId  <br>
     * @param [in] video_stream_profile, �����ȵ�λ  <br>
     */
    virtual void onFirstVideoFrameArrived(const char* pod_id, int video_stream_profile) {
        (void)pod_id;
        (void)video_stream_profile;
    }

    /**
     * @type callback
     * @brief ���ֻ�ֹͣ�ص�
     * @param [in] pod_id, �Զ�podId  <br>
     */
    virtual void onStop(const char* pod_id) {
        (void)pod_id;
    }


    /**
     * @type callback
     * @brief SDK�ڲ������Ĵ���ص�
     * @param [in] user_id, Զ���û�ID  <br>
     * @param [in] code���ο��������ĵ�
     * @param [in] msg��������Ϣ
     */
    virtual void onError(const char* pod_id, int code, const char* msg) {
        (void)pod_id;
        (void)code;
        (void)msg;
    }

    /**
     * @type callback
     * @brief SDK�ڲ������ľ���ص�
     * @param [in] user_id, Զ���û�ID  <br>
     * @param [in] code���ο��������ĵ�
     * @param [in] msg��������Ϣ
     */
    virtual void onWarning(const char* pod_id, int code, const char* msg) {
        (void)pod_id;
        (void)code;
    }


    ///**
    // * @type callback
    // * @brief �ƶ�pod��Ļ��ת
    // * @param [in] rotation, ����: 0��180������: 90��270
    // * @note ����{@link vephone_engine#rotateScreen(vecommon::RotateDegree degree)}�ɹ����ص���     <br>
    // *          +   ��ʱ������Ⱦ�����Ѿ��ı䣬����ͨ���˻ص����������֡���С������Ƚ��иı�     <br>
    // *
    // */
    //virtual void onRemoteRotation(const char* pod_id, int rotation) {
    //    (void)pod_id;
    //    (void)rotation;
    //}
};