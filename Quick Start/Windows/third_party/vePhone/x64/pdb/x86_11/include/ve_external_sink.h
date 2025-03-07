#pragma once
#include <stdint.h>


namespace vecommon {

/**
 * @type type
 * @brief 视频帧回调信息
 */
class VeExtVideoFrame {

public:

    ~VeExtVideoFrame() = default;

    /**
     * @brief 获取视频帧时间戳，单位：微秒
     */
    virtual int64_t timestampUs() const = 0;

    /**
     * @brief 获取视频帧宽度，单位：px
     */
    virtual int width() const = 0;

    /**
     * @brief 获取视频帧高度，单位：px
     */
    virtual int height() const = 0;

    /**
     * @brief 视频帧颜色 plane 数量
     *
     * @notes RGBA / ARGB/ BGRA 格式下返回 1     <br>
     *        YUV 数据存储格式分为打包（packed）存储格式和平面（planar）存储格式 <br>
     *        +   planar 格式中 Y、U、V 分平面存储    <br>
     *        +   packed 格式中 Y、U、V 交叉存储
     */
    virtual int numberOfPlanes() const = 0;

    /**
     * @brief 获取 plane 数据指针
     * @param [in] planeIndex plane数据索引
     *
     * @note 获取ARGB/RGBA/BGRA格式数据，getPlaneData(0)   <br>
     *   +    获取YUVI420格式数据，(Y)getPlaneData(0) \ (U)getPlaneData(1) \ (V)getPlaneData(2)
     */
    virtual uint8_t* getPlaneData(int planeIndex) = 0;

    /**
     * @brief 获取 plane 中数据行的长度(步幅)
     * @param [in] planeIndex plane 数据索引
     *
     * @note 获取ARGB/RGBA/BGRA格式数据，getPlaneStride(0)   <br>
     *   +   获取YUVI420格式数据Stride，(Y)getPlaneStride(0) \ (U)getPlaneStride(1) \ (V)getPlaneStride(2)
     */
    virtual int getPlaneStride(int planeIndex) = 0;
    
};


/**
 * @locale zh
 * @type callback
 * @brief 外部渲染器类
 */
class VeExternalSink {
public:

    /**
     * @brief 视频帧回调
     * @param videoFrame 视频帧实例
     */
    virtual void onFrame(VeExtVideoFrame* videoFrame) {
        (void)videoFrame;
    }

};

} // namespace vecommon