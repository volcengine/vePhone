#pragma once
#include "pch.h"
#include "verender_cloudx.h"


static const int CHILD_WIDTH = 36;
static const int CHILD_HEIGHT = 64;
static const int CHILD_MARING = 3;

static const int PLAY_WIND_WIDTH = 240;
static const int PLAY_WIND_HEIGHT = 424;


class QkExternalSink : public VeExternalSink {
public:
	void onFrame(VeExtVideoFrame* frame) override;
	void setCanvas(HWND win);

private:
	HWND _window = nullptr;
};


class QkSessionListener : public ISessionListener {
public:
	QkSessionListener(const char* podId, vecommon::PhoneSessionConfig config, HWND hwnd)
		:_podId(podId), _config(config), _hwnd(hwnd), _session(nullptr) {
	};
	~QkSessionListener() = default;

	// override: ISessionListener
	void onStartSuccess(int video_stream_profile, const char* round_id, const char* target_id, const char* reserved_id, const char* plan_id) override;
	void onStop() override;
	void onFirstVideoFrame(const vecommon::VideoFrameInfo& info) override;
	void onVideoStreamProfileChange(bool result, int from, int to) override;
	void onError(int code, const char* msg) override;
	void onPodExited(int reason, const char* msg) override;
	void onPodJoined(const char* podUserId) override;
	void onRemoteRotation(int rotation) override;
	void onLocalScreenRotate(vecommon::RotateDegree degree) override;
	void onAutoRecycleTimeCallBack(int seconds) override;
	void onShakeResponse(int result, const char* msg) override;
	void onAudioInjectionResponse(int result, const char* msg) override;
	void onScreenShot(int result, const char* savePath, const char* downloadUrl) override;
	void onNavBarStatus(int status, int reason) override;

	void setSession(PhoneSession* session);
	void rotateScreen(vecommon::RotateDegree degree, bool withPod);
	void resizeWindow(bool shouldLocalLandscape); // ���㲢������ת��Ĵ��ڴ�С shouldLocalLandscape--���ش����Ƿ�Ӧ��תΪ����

private:
	const char* _podId = nullptr;
	PhoneSession* _session = nullptr;
	vecommon::PhoneSessionConfig _config;
	HWND _hwnd;
	vecommon::RotateDegree _rotationLocalDegree = vecommon::RotateDegree::DEGREE_0;
	bool _isLocalLandscape = false;
	bool _isRemoteLandscape = false;
};