#pragma once
#include "pch.h"
#include "verender_cloudx.h"
#include "ve_qk_class.h"
#include "msg_processor.h"
#include <gdiplus.h>


class QkDemo : public IEventSyncListener, BatchControlListener, ISupportFeatureListener {
public:
	QkDemo(int cmd, HWND mainWnd, HINSTANCE instance);
	~QkDemo() = default;

	int WndProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam);
	void ProcessCmd(HWND hWnd, WPARAM wParam, LPARAM lParam);

	// override: BatchControlListener
	void onBatchPodStartResult(int code, const char* msg, const std::vector<vecommon::PodInfo>* pod_list, const std::vector<vecommon::PodError>* pod_errors) override;
	void onStartSuccess(const char* pod_id) override;
	void onPodJoin(const char* pod_id) override;
	void onFirstVideoFrameArrived(const char* pod_id, int video_stream_profile) override;
	void onStop(const char* pod_id) override;
	void onError(const char* pod_id, int code, const char* msg) override;
	void onWarning(const char* pod_id, int code, const char* msg) override;

	// override: IEventSyncListener
	void onEventSyncError(int code, const char* msg) override;
	void onMasterJoinRoomSuccess() override;
	void onContorlledUserJoined(const char* userId, const char* roomId) override;
	void onContorlledUserLeave(const char* userId, const char* roomId) override;

	// override: ISupportFeatureListener
	void onSupportFeatureResult(vecommon::Feature feature, int code, const char* msg) override;

	void initCloudRenderX();
	void releaseCloudRenderX();
	void initBcvConfig();
	void reqBatchPodStart();
	void start();
	void stop();
	void startEventSync();
	void stopEventSync();
	void checkIfSupportWallpaper();
	void readConfigIni();

	HWND _mainWindow = nullptr;
	const int _cmdShowValue;
	HINSTANCE _instance = nullptr;
	bool _isMenuShow = false;

	Gdiplus::GdiplusStartupInput _gdiplusStartupInput;
	ULONG_PTR _gdiplusToken;

	WCHAR _szTitle[100];                  // �������ı�
	WCHAR _szWindowClass[100];            // ����������

	int _mainWindowHeight = 0;
	int _mainWindowWidth = 0;
	int _lineWindowCount = 0;
	int _lineCount = 0;

	std::unordered_map<const char*, vecommon::PhoneSessionConfig> _phoneConfigs;
	std::unordered_map<std::string, HWND> _podIdToPreWnd;  // podId->Ԥ����
	std::unordered_map<std::string, HWND> _podIdToLargeWnd; // podId->��
	std::unordered_map<PhoneSession*, std::string> _sessionToPodId; // session->podId
	std::unordered_map<std::string, PhoneSession*> _podIdToSession; // podId->session
	std::unordered_map<PhoneSession*, QkSessionListener*> _sessionToListener; // session->listener

	vecommon::VeCloudRenderX* _renderX = nullptr;
	BatchControlVideo* _batchControlVideo = nullptr;
	std::string _eventSyncRoundId, _eventSyncUserId;
	std::string _bcvRoundId, _bcvUserId; // _bcvUserId��_sessionUserId��Ҫʹ�ò�ͬ��userId�Խ�������
	std::string _sessionRoundId, _sessionUserId;
	std::vector<std::string> _podIdList;
	std::vector<HWND> _preWndList;

	std::string _accountId, _ak, _sk, _token, _productId;

	RECT _validArea; // ��Ч����
	PhoneSession* _focusedSession = nullptr; // ��ǰ��ȡ�����session

	HWND createPreviewWindow(const char* pod_id); // ����Ԥ������
	void updateValidArea(HWND mainWnd); // ������Ч����

private:
	
	vecommon::EventSyncConfig _eventSyncConfig;
	vecommon::PhoneSessionConfig _sessionConfig;
	vecommon::BatchControlVideoConfig _bcvConfig;
	vecommon::SupportFeatureConfig _supportFeatureConfig;
};

static std::shared_ptr<QkDemo> gDemo;
std::shared_ptr<QkDemo> getDemo();