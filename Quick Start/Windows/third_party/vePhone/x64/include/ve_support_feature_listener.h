#pragma once


class ISupportFeatureListener {
public:
	/*
	* @type callback
	* @brief �Ƿ�֧��ĳ�����ԵĻص�
	* @param [in] feature ����
	*			   0 -- ��ֽ��
	* @param [in] code ������
	*			   0 -- SUCCESS
	*			  -1 -- LIST_POD_REQUEST_FAILED
	*			  -2 -- LIST_POD_PARSE_RESPONSE_FAILED
	*			  -3 -- POD_IMAGE_NOT_SUPPORT
	*			  -4 -- GET_PREVIEW_SETTING_PARSE_RESPONSE_FAILED
	*			  -5 -- EMPTY_SOFTWARE_VERSION
	* @param [in] msg ������Ϣ
	*/
	virtual void onSupportFeatureResult(vecommon::Feature feature, int code, const char* msg) {
	}

};