package com.example.sdkdemo.util;


import android.content.Context;
import android.os.SystemClock;
import android.text.TextUtils;

import androidx.annotation.NonNull;
import androidx.core.util.Consumer;

import com.volcengine.common.SDKContext;
import com.volcengine.phone.VePhoneEngine;

import org.json.JSONObject;

public class SdkUtil {


    /**
     * 需在manifest文件中配置accountId
     */
    public static boolean checkHasConfigAccountIdInManifest() {
        return !TextUtils.isEmpty(SDKContext.getAccountId());
    }


    /**
     * <p>ak/sk/token用于用户鉴权，获取方式详见README[鉴权相关/获取临时密钥]</p>
     *
     * - 方案验证和集成阶段：<br>
     * 可以按文档指引，在创建具备相应权限的子账号后，在「控制台左侧导航栏」点击「新手入门」，选择存储方案后点击「生成临时鉴权密钥」
     * 使用生成的临时ak、sk、token进行start拉流
     * <br>
     * - 正式技术方案阶段：<br>
     * 业务侧服务端负责调用火山STS接口为客户端生成鉴权密钥，客户端从服务端获取到临时ak、sk、token后进行start拉流<br>
     * <p><font color='red'>Note: manifest中的VOLC_ACCOUNT_ID信息也是鉴权的一部分，须替换为您的accountId</font></p>
     * @docs <a href="https://www.volcengine.com/docs/6394/1262151?lang=zh">获取临时密钥（STS）</a>
     */
    public static @NonNull PlayAuth getPlayAuth(Context context) {
        PlayAuth auth = new PlayAuth();
        try {
            // TODO: 到火山云手机官网获取您的账户和资源信息进行参数替换
            JSONObject stsJObj = new JSONObject(AssetsUtil.getTextFromAssets(context, "sts.json"));
            return new PlayAuth(
                    stsJObj.getString("ak"),
                    stsJObj.getString("sk"),
                    stsJObj.getString("token"),
                    stsJObj.getString("productId"),
                    stsJObj.getString("podId")
            );
        } catch (Throwable ignore) {
        }
        return auth;
    }


    public static void checkPlayAuth(@NonNull PlayAuth auth, Consumer<PlayAuth> onSuccess, Consumer<PlayAuth> onFail) {
        if (auth.isInvalid()) {
            onFail.accept(auth);
        } else {
            onSuccess.accept(auth);
        }
    }

    /**
     * 生成客户端用户id
     * 推荐采用：`{OS}_{DEVICE_ID}`的格式用于区分不同系统和设备，防止出现预期外的userId重复
     * 补充：当不同端的userId重复时，会发生冲突，表现为后进房的客户端会把先进房的客户端踢出房间
     */
    public @NonNull static String getClientUid() {
        return "android_github_" + VePhoneEngine.getInstance().getDeviceId();
    }

    /**
     * 业务会话id，非必填项
     */
    public @NonNull static String getRoundId() {
        return VePhoneEngine.getInstance().getDeviceId() + SystemClock.uptimeMillis();
    }

    public static class PlayAuth {
        public String ak, sk, token, productId, podId;

        public PlayAuth() {
        }

        public PlayAuth(String ak, String sk, String token, String productId, String podId) {
            this.ak = ak;
            this.sk = sk;
            this.token = token;
            this.productId = productId;
            this.podId = podId;
        }

        public boolean isInvalid() {
            return TextUtils.isEmpty(ak) || TextUtils.isEmpty(sk) || TextUtils.isEmpty(token) || TextUtils.isEmpty(productId) || TextUtils.isEmpty(podId);
        }

        @Override
        public @NonNull String toString() {
            return "ak='" + ak + '\'' +
                    "\nsk='" + sk + '\'' +
                    "\ntoken='" + token + '\'' +
                    "\nproductId='" + productId + '\'' +
                    "\npodId='" + podId + '\'';
        }
    }
}
