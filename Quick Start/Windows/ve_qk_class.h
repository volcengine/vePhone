#pragma once
#include "pch.h"
#include "ve_render_cloudx.h"
#include <mmeapi.h>


static const int CHILD_WIDTH = 36;
static const int CHILD_HEIGHT = 64;
static const int CHILD_MARING = 3;

static const int PLAY_WIND_WIDTH = 240;
static const int PLAY_WIND_HEIGHT = 424;


class QkExternalSink : public vecommon::VeExternalVideoSink {
public:
	void onVideoFrame(vecommon::VeExtVideoFrame* frame) override;
	void setCanvas(HWND win);

private:
	HWND _window = nullptr;
};


class QkSessionListener : public vecommon::ISessionListener, public vecommon::VeExternalVideoSink , public vecommon::VeExternalAudioSink {
public:
	QkSessionListener(const char* podId, vecommon::PhoneSessionConfig config, HWND hwnd)
		:_podId(podId), _config(config), _hwnd(hwnd), _session(nullptr) {
	};
	~QkSessionListener() = default;

	// override: ISessionListener
	void onStartSuccess(int video_stream_profile, const char* round_id, const char* target_id, const char* reserved_id, const char* plan_id) override;
	void onStop() override;
	void onFirstAudioFrame(const vecommon::AudioFrameInfo& info) override;
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

	// override: VeExternalVideoSink
	void onVideoFrame(vecommon::VeExtVideoFrame* videoFrame) override;

	// override: VeExternalAudioSink
	void onAudioFrame(vecommon::VeExtAudioFrame* audioFrame) override;

	void setSession(vecommon::PhoneSession* session);
	void rotateScreen(vecommon::RotateDegree degree, bool withPod);
	void resizeWindow(bool shouldLocalLandscape); // 计算并更新旋转后的窗口大小 shouldLocalLandscape--本地窗口是否应旋转为横屏

	void configAudioParams(uint32_t sampleRate, uint16_t channels, uint16_t bitDepth, uint16_t frameSize);
	bool initAudioRes();
	bool uninitAudioRes();
	void playAudio(LPWAVEHDR hdr);
	void sendToDevice(const uint8_t* frame, size_t size);

	HWAVEOUT _waveOut{ 0 };

	std::vector<WAVEHDR> _waveHdrList;
	int _waveHdrListSize = 8; // 使用8个可以正常播放音频，少的话会卡回调线程
	std::atomic<bool> _isPlaying{ false }; // is playing the audio stream?
	std::mutex _mtxAudio;

	uint32_t _sampleRate = 0;   // 采样率
	uint16_t _channels = 0;     // 通道数
	uint16_t _bitDepth = 0;     // 位深
	uint16_t _frameSize = 0;    // 帧长度

private:
	const char* _podId = nullptr;
	vecommon::PhoneSession* _session = nullptr;
	vecommon::PhoneSessionConfig _config;
	HWND _hwnd;
	vecommon::RotateDegree _rotationLocalDegree = vecommon::RotateDegree::DEGREE_0;
	bool _isLocalLandscape = false;
	bool _isRemoteLandscape = false;
};