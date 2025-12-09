package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.cloudphone.apiservice.AppGroundSwitchManager;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.util.List;
import java.util.Map;

/**
 * 该类用于展示与云端应用切换前后台{@link AppGroundSwitchManager}相关的功能接口的使用方法
 */
public class AppGroundSwitchManagerActivity extends BasePlayActivity {

    private ViewGroup mContainer;
    private AppGroundSwitchManager mAppGroundSwitchManager;
    private SwitchCompat mSwShowOrHide;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnSetRemoteAppForeground, mBtnGetRemoteBackgroundAppList;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_app_ground_switch);
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mBtnSetRemoteAppForeground = findViewById(R.id.btn_set_remote_app_foreground);
        mBtnGetRemoteBackgroundAppList = findViewById(R.id.btn_get_remote_background_app_list);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        /**
         * 手动切换云端应用到前台
         * void setRemoteAppForeground(String packageName)
         *
         * @param packageName 云端应用包名
         */
        mBtnSetRemoteAppForeground.setOnClickListener(v -> {
            if (mAppGroundSwitchManager != null) {
                mAppGroundSwitchManager.setRemoteAppForeground("com.android.settings");
            }
            else {
                Log.e(TAG, "mAppGroundSwitchManager == null");
            }
        });

        /**
         * 获取云端在后台的应用列表
         * void getRemoteBackgroundAppList()
         */
        mBtnGetRemoteBackgroundAppList.setOnClickListener(v -> {
            if (mAppGroundSwitchManager != null) {
                mAppGroundSwitchManager.getRemoteBackgroundAppList();
            }
            else {
                Log.e(TAG, "mAppGroundSwitchManager == null");
            }
        });
    }

    private void initPlayConfigAndStartPlay() {
        SdkUtil.PlayAuth auth = SdkUtil.getPlayAuth(this);
        String roundId = "roundId_123";
        PhonePlayConfig.Builder builder = new PhonePlayConfig.Builder();
        builder.userId(SdkUtil.getClientUid())
                .ak(auth.ak)
                .sk(auth.sk)
                .token(auth.token)
                .container(mContainer)
                .enableLocalKeyboard(true)
                .roundId(roundId)
                .podId(auth.podId)
                .productId(auth.productId)
                .streamListener(this);
        VePhoneEngine.getInstance().start(builder.build(), this);
    }

    @Override
    protected void onResume() {
        super.onResume();
        VePhoneEngine.getInstance().resume();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onPause() {
        super.onPause();
        VePhoneEngine.getInstance().pause();
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
    }

    @Override
    public void finish() {
        VePhoneEngine.getInstance().stop();
        super.finish();
    }

    /**
     * 加入房间前回调，用于获取并初始化各个功能服务，例如设置各种事件监听回调。
     */
    @Override
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        super.onServiceInit(extras);
        mAppGroundSwitchManager = VePhoneEngine.getInstance().getAppGroundSwitchManager();
        if (mAppGroundSwitchManager != null) {
            mAppGroundSwitchManager.setGroundChangeListener(new AppGroundSwitchManager.AppGroundSwitchedListener() {
                /**
                 * 云端实例中的应用切换到后台的回调
                 *
                 * @param switchType 切换的类型，1表示自动切换，0表示客户端主动切换。
                 * @param packageName 切换前后台的应用包名
                 */
                @Override
                public void onRemoteAppSwitchedBackground(int switchType, String packageName) {
                    Log.i(TAG, "[onRemoteAppSwitchedBackground] switchType: " + switchType + ", packageName: " + packageName);
                }

                /**
                 * 云端实例中的应用切换到前台的回调
                 *
                 * @param switchType 切换的类型，1表示自动切换，0表示客户端主动切换。
                 * @param packageName 切换前后台的应用包名
                 */
                @Override
                public void onRemoteAppSwitchedForeground(int switchType, String packageName) {
                    Log.i(TAG, "[onRemoteAppSwitchedForeground] switchType: " + switchType + ", packageName: " + packageName);
                }

                /**
                 * 云端实例中的应用切换前后台失败的回调
                 *
                 * @param errorCode 错误码
                 * @param errorMessage 错误信息
                 */
                @Override
                public void onRemoteGameSwitchedFailed(int errorCode, String errorMessage) {
                    Log.i(TAG, "[onRemoteGameSwitchedFailed] errorCode: " + errorCode + ", errorMessage: " + errorMessage);
                }

                /**
                 * 获取云端在后台的应用列表的回调
                 *
                 * @param packageNameList 应用包名的列表
                 */
                @Override
                public void onRevicedRemoteAppList(List<String> packageNameList) {
                    Log.i(TAG, "[onReceivedRemoteAppList] packageNameList: " + packageNameList);
                }
            });
        }
        else {
            Log.e(TAG, "mAppGroundSwitchManager == null");
        }
    }
}
