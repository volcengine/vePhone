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
     * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *
     * ak/sk/token用于用户鉴权，需要从火山官网上获取，具体步骤详见README[鉴权相关]。
     * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *
     *
     * ak/sk/token/podId的值从assets目录下的sts.json文件中读取，该目录及文件需要自行创建。
     * sts.json的格式形如
     * {
     *     "podId": "your_pod_id",
     *     "productId": "your_product_id",
     *     "ak": "your_ak",
     *     "sk": "your_sk",
     *     "token": "your_token"
     * }
     */
    public static @NonNull PlayAuth getPlayAuth(Context context) {
        PlayAuth auth = new PlayAuth();
        try {
            // TODO: 到火山云手机官网获取您的账户和资源信息进行参数替换
            // Note: manifest中的VOLC_ACCOUNT_ID信息也须替换为您的accountId
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
     */
    public @NonNull static String getClientUid() {
        return "android_github_" + VePhoneEngine.getInstance().getDeviceId();
    }


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
