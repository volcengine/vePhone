#pragma once


class ISupportFeatureListener {
public:
	/*
	* @type callback
	* @brief 是否支持某个特性的回调
	* @param [in] feature 特性
	*			   0 -- 壁纸流
	* @param [in] code 错误码
	*			   0 -- SUCCESS
	*			  -1 -- LIST_POD_REQUEST_FAILED
	*			  -2 -- LIST_POD_PARSE_RESPONSE_FAILED
	*			  -3 -- POD_IMAGE_NOT_SUPPORT
	*			  -4 -- GET_PREVIEW_SETTING_PARSE_RESPONSE_FAILED
	*			  -5 -- EMPTY_SOFTWARE_VERSION
	* @param [in] msg 错误信息
	*/
	virtual void onSupportFeatureResult(vecommon::Feature feature, int code, const char* msg) {
	}

};