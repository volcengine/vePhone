#pragma once
#include "pch.h"
#include "ve_render_cloudx.h"
#include "ve_qk_class.h"
#include "msg_processor.h"
#include <gdiplus.h>


class QkDemo : public vecommon::IEventSyncListener, vecommon::BatchControlListener, vecommon::ISupportFeatureListener {
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
	void onEventSyncError(int code, const char* msg, const char* userId) override;
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

	WCHAR _szTitle[100];                  // 标题栏文本
	WCHAR _szWindowClass[100];            // 主窗口类名

	int _mainWindowHeight = 0;
	int _mainWindowWidth = 0;
	int _lineWindowCount = 0;
	int _lineCount = 0;

	std::unordered_map<const char*, vecommon::PhoneSessionConfig> _phoneConfigs;
	std::unordered_map<std::string, HWND> _podIdToPreWnd;  // podId->预览窗
	std::unordered_map<std::string, HWND> _podIdToLargeWnd; // podId->大窗
	std::unordered_map<vecommon::PhoneSession*, std::string> _sessionToPodId; // session->podId
	std::unordered_map<std::string, vecommon::PhoneSession*> _podIdToSession; // podId->session
	std::unordered_map<vecommon::PhoneSession*, QkSessionListener*> _sessionToListener; // session->listener

	vecommon::VeCloudRenderX* _renderX = nullptr;
	vecommon::BatchControlVideo* _batchControlVideo = nullptr;
	std::string _eventSyncRoundId, _eventSyncUserId;
	std::string _bcvRoundId, _bcvUserId; // _bcvUserId和_sessionUserId需要使用不同的userId以进行区分
	std::string _sessionRoundId, _sessionUserId;
	std::vector<std::string> _podIdList;
	std::vector<HWND> _preWndList;

	std::string _accountId, _ak, _sk, _token, _productId;

	RECT _validArea; // 有效区域
	vecommon::PhoneSession* _focusedSession = nullptr; // 当前获取焦点的session

	HWND createPreviewWindow(const char* pod_id); // 创建预览窗口
	void updateValidArea(HWND mainWnd); // 更新有效区域

private:
	
	vecommon::BatchControlVideoConfig _bcvConfig;

};

static std::shared_ptr<QkDemo> gDemo;
std::shared_ptr<QkDemo> getDemo();