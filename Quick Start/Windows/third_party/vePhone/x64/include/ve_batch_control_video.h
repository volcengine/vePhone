#pragma once
#include "ve_type_defines.h"
#include "ve_batch_control_listener.h"
#include "ve_external_sink.h"

class BatchControlVideo
{
public:

    BatchControlVideo(const vecommon::BatchControlVideoConfig& config) :_config(config) {};
    virtual ~BatchControlVideo() = default;

    // ����С���ӷ�����
    // - ��ȡpodList�뷿���Ӧ��ϵ
    // - ��ȡ�ӷ���Ȩ��Ϣ
    virtual int requestBatchPodStart() = 0;

    // ��������pod����
    // 1. ��������
    // 2. �ӷ�
    virtual int start() = 0;

    // �˳�����pod���䲢��������
    // 1. �˷�
    // 2. ��������
    virtual int stop() = 0;

    /// <summary>
    /// ��ȡ������Ƶ��״̬
    /// </summary>
    /// <param name="pod_id">ָ��Ҫ��ѯ��podId</param>
    /// <returns></returns>
    virtual vecommon::SessionStatus getVideoStatus(const char* pod_id) { return vecommon::SessionStatus::Idle; };

    /// <summary>
    /// ��ȡָ��pod����Ƶ����
    /// </summary>
    /// <param name="pod_id">ָ��Ҫ��ѯ��podId</param>
    /// <returns></returns>
    virtual vecommon::ControlVideoConfig* getVideoConfig(const char* pod_id) = 0;

    /// <summary>
    /// ������Ƶ
    /// </summary>
    /// <param name="pod_id">ָ��Ҫ������podId</param>
    virtual int subscribe(const char* pod_id) = 0;


    /// <summary>
    /// �˶���Ƶ
    /// </summary>
    /// <param name="pod_id">ָ��Ҫ������podId</param>
    virtual int unsubscribe(const char* pod_id) = 0;

    /// <summary>
    /// ��ȡ������Ƶ����״̬
    /// </summary>
    /// <param name="pod_id">ָ��Ҫ��ѯ��podId</param>
    /// <returns></returns>
    virtual bool isSubscribed(const char* pod_id) = 0;

    /// <summary>
    /// ��ȡ������Ƶ�Զ�����״̬
    /// </summary>
    /// <param name="pod_id">ָ��Ҫ��ѯ��podId</param>
    /// <returns>true-�Զ����ģ�false-�ֶ�����</returns>
    virtual bool isAutoSubscribe(const char* pod_id) = 0;

    /// <summary>
    /// ���µ�����Ƶ����Ⱦ����
    /// </summary>
    /// <param name="pod_id">ָ��Ҫ������podId</param>
    /// <param name="canvas">��Ⱦ����</param>
    virtual int updateCanvas(const char* pod_id, void* canvas) = 0;

    /// <summary>
    /// �����ⲿ��Ⱦ��
    /// </summary>
    /// <param name="pod_id"></param>
    /// <param name="externalSink"></param>
    virtual int setExternalSink(const char* pod_id, VeExternalSink* externalSink) = 0;

    /// <summary>
    /// ��ȡ�ⲿ��Ⱦ��
    /// </summary>
    /// <param name="pod_id"></param>
    /// <returns></returns>
    virtual VeExternalSink* getExternalSink(const char* pod_id) = 0;

    /// <summary>
    /// ����Ⱥ���¼��ص�
    /// </summary>
    /// <param name="listener"></param>
    virtual void setBatchControlListener(BatchControlListener* listener) = 0;

protected:
    const vecommon::BatchControlVideoConfig& _config;


};

