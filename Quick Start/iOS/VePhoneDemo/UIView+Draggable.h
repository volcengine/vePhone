//
//  UIView+Draggable.h
//  DraggableViewDemo
//
//  Created by anjohnlv on 2017/9/4.
//  Copyright © 2017年 anjohnlv. All rights reserved.
//

#import <UIKit/UIKit.h>

/**
 拖拽方式
 - DraggingTypeDisabled :不能拖拽
 - DraggingTypeNormal: 正常拖拽
 - DraggingTypeRevert: 释放后还原
 - DraggingTypePullOver: 自动靠边,只会靠左右两边
 - DraggingTypeAdsorb: 靠边时自动吸附边缘，可吸附四周
 */
typedef NS_ENUM(NSUInteger, DraggingType) {
    DraggingTypeDisabled,
    DraggingTypeNormal,
    DraggingTypeRevert,
    DraggingTypePullOver,
    DraggingTypeAdsorb,
};

@protocol DraggingDelegate <NSObject>

-(void)draggingDidBegan:(UIView *)view;
-(void)draggingDidChanged:(UIView *)view;
-(void)draggingDidEnded:(UIView *)view;

@end

@interface UIView (Draggable)<UIGestureRecognizerDelegate>

/**
 拖拽事件委托，可监听拖拽的开始、变化以及结束事件。
 */
@property (weak, nonatomic) id<DraggingDelegate> delegate;

/**
 拖拽方式，默认是DraggingTypeDisabled。
 */
@property(nonatomic)DraggingType draggingType;
/**
 是否可只能在subView的范围内，默认是NO。
 
 @warning 如果NO，超出subView范围的部分无法响应拖拽。剪裁超出部分可直接使用superView.clipsToBounds=YES
 */
@property(nonatomic)BOOL draggingInBounds;

/**
 主动靠边并吸附
 */
-(void)adsorbingAnimated:(BOOL)animated;

/**
 主动靠边
 */
-(void)pullOverAnimated:(BOOL)animated;

/**
 主动还原位置
 */
-(void)revertAnimated:(BOOL)animated;
@end
