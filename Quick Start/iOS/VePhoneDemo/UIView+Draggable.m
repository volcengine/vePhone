//
//  UIView+Draggable.m
//  DraggableViewDemo
//
//  Created by anjohnlv on 2017/9/4.
//  Copyright © 2017年 anjohnlv. All rights reserved.
//

#import "UIView+Draggable.h"
#import <objc/runtime.h>

static const void *kPanKey           = @"panGestureKey";
static const void *kDelegateKey      = @"delegateKey";
static const void *kTypeKey          = @"draggingTypeKey";
static const void *kInBoundsKey      = @"inBoundsKey";
static const void *kRevertPointKey   = @"revertPointKey";
static const NSInteger kAdsorbingTag = 10000;
static const CGFloat kAdsorbScope    = 2.f;
static const CGFloat kAdsorbDuration = 0.5f;

@implementation UIView (Draggable)

#pragma mark - synthesize

- (UIPanGestureRecognizer *)panGesture
{
    return objc_getAssociatedObject(self, kPanKey);
}

- (void)setPanGesture:(UIPanGestureRecognizer *)panGesture
{
    objc_setAssociatedObject(self, kPanKey, panGesture, OBJC_ASSOCIATION_ASSIGN);
}

- (id<DraggingDelegate>)delegate
{
    return objc_getAssociatedObject(self, kDelegateKey);
}

- (void)setDelegate:(id<DraggingDelegate>)delegate
{
    objc_setAssociatedObject(self, kDelegateKey, delegate, OBJC_ASSOCIATION_ASSIGN);
}

- (DraggingType)draggingType
{
    return [objc_getAssociatedObject(self, kTypeKey) integerValue];
}

- (void)setDraggingType:(DraggingType)draggingType
{
    if ([self draggingType] == DraggingTypeAdsorb) {
        [self bringViewBack];
    }
    objc_setAssociatedObject(self, kTypeKey, [NSNumber numberWithInteger: draggingType], OBJC_ASSOCIATION_ASSIGN);
    [self makeDraggable: !(draggingType == DraggingTypeDisabled)];
    switch (draggingType) {
        case DraggingTypePullOver:
            [self pullOverAnimated: YES];
            break;
        case DraggingTypeAdsorb:
            [self adsorb];
            break;
        default:
            break;
    }
}

- (BOOL)draggingInBounds
{
    return [objc_getAssociatedObject(self, kInBoundsKey) boolValue];
}

- (void)setDraggingInBounds:(BOOL)draggingInBounds
{
    objc_setAssociatedObject(self, kInBoundsKey, [NSNumber numberWithBool: draggingInBounds], OBJC_ASSOCIATION_ASSIGN);
}

- (CGPoint)revertPoint
{
    NSString *pointString = objc_getAssociatedObject(self, kRevertPointKey);
    CGPoint point = CGPointFromString(pointString);
    return point;
}

- (void)setRevertPoint:(CGPoint)revertPoint
{
    NSString *point = NSStringFromCGPoint(revertPoint);
    objc_setAssociatedObject(self, kRevertPointKey, point, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
}

#pragma mark - Draggable

- (void)makeDraggable:(BOOL)draggable
{
    [self setUserInteractionEnabled: YES];
    [self removeConstraints: self.constraints];
    for (NSLayoutConstraint *constraint in self.superview.constraints) {
        if ([constraint.firstItem isEqual: self]) {
            [self.superview removeConstraint: constraint];
        }
    }
    [self setTranslatesAutoresizingMaskIntoConstraints: YES];
    UIPanGestureRecognizer *panGesture = [self panGesture];
    if (draggable) {
        if (!panGesture) {
            panGesture = [[UIPanGestureRecognizer alloc] initWithTarget: self action: @selector(pan:)];
            panGesture.delegate = self;
            [self addGestureRecognizer: panGesture];
            [self setPanGesture: panGesture];
        }
    } else {
        if (panGesture) {
            [self setPanGesture: nil];
            [self removeGestureRecognizer: panGesture];
        }
    }
}

- (void)pan:(UIPanGestureRecognizer *)panGestureRecognizer
{
    switch (panGestureRecognizer.state) {
        case UIGestureRecognizerStateBegan:
        {
            [self bringViewBack];
            [self setRevertPoint: self.center];
            [self dragging: panGestureRecognizer];
            [self.delegate draggingDidBegan: self];
        }
            break;
        case UIGestureRecognizerStateChanged:
        {
            [self dragging: panGestureRecognizer];
            [self.delegate draggingDidChanged: self];
        }
            break;
        case UIGestureRecognizerStateEnded:
        {
            switch ([self draggingType]) {
                case DraggingTypeRevert:
                {
                    [self revertAnimated: YES];
                }
                    break;
                case DraggingTypePullOver:
                {
                    [self pullOverAnimated: YES];
                }
                    break;
                case DraggingTypeAdsorb:
                {
                    [self adsorb];
                }
                    break;
                default:
                    break;
            }
            [self.delegate draggingDidEnded: self];
        }
            break;
        default:
            break;
    }
}

- (void)dragging:(UIPanGestureRecognizer *)panGestureRecognizer
{
    UIView *view = panGestureRecognizer.view;
    CGPoint translation = [panGestureRecognizer translationInView: view.superview];
    CGPoint center = CGPointMake(view.center.x + translation.x, view.center.y + translation.y);
    if ([self draggingInBounds]) {
        CGSize size = view.frame.size;
        CGSize superSize = view.superview.frame.size;
        CGFloat width = size.width;
        CGFloat height = size.height;
        CGFloat superWidth = superSize.width;
        CGFloat superHeight = superSize.height;
        center.x = (center.x < width / 2) ? width / 2 : center.x;
        center.x = (center.x + width / 2 > superWidth) ? superWidth - width / 2 : center.x;
        center.y = (center.y < height / 2) ? height / 2: center.y;
        center.y = (center.y + height / 2 > superHeight) ? superHeight - height / 2 : center.y;
    }
    [view setCenter: center];
    [panGestureRecognizer setTranslation: CGPointZero inView: view.superview];
}

#pragma mark - pull over

- (void)pullOverAnimated:(BOOL)animated
{
    [self bringViewBack];
    CGPoint center = [self centerByPullOver];
    [UIView animateWithDuration: animated ? kAdsorbDuration : 0 animations: ^{
        [self setCenter: center];
    } completion: nil];
}

- (CGPoint)centerByPullOver
{
    CGPoint center = [self center];
    CGSize size = self.frame.size;
    CGSize superSize = [self superview].frame.size;
    if (center.x < superSize.width / 2) {
        center.x = size.width / 2;
    } else {
        center.x = superSize.width - size.width / 2;
    }
    if (center.y < size.height / 2) {
        center.y = size.height / 2;
    } else if (center.y > superSize.height - size.height / 2){
        center.y = superSize.height - size.height / 2;
    }
    return center;
}

#pragma mark - revert

- (void)revertAnimated:(BOOL)animated
{
    [self bringViewBack];
    CGPoint center = [self revertPoint];
    [UIView animateWithDuration: animated ? kAdsorbDuration : 0 animations: ^{
        [self setCenter: center];
    } completion:nil];
}

#pragma mark - adsorb

- (void)adsorbingAnimated:(BOOL)animated
{
    if (self.superview.tag == kAdsorbingTag) {
        return;
    }
    CGPoint center = [self centerByPullOver];
    [UIView animateWithDuration:animated?kAdsorbDuration: 0 animations: ^{
        [self setCenter: center];
    } completion: ^(BOOL finish){
        [self adsorbAnimated: animated];
    }];
}

- (void)adsorb
{
    if (self.superview.tag == kAdsorbingTag) {
        return;
    }
    CGPoint origin = self.frame.origin;
    CGSize size = self.frame.size;
    CGSize superSize = self.superview.frame.size;
    BOOL adsorbing = NO;
    if (origin.x < kAdsorbScope) {
        origin.x = 0;
        adsorbing = YES;
    }else if (origin.x > superSize.width - size.width - kAdsorbScope){
        origin.x = superSize.width - size.width;
        adsorbing = YES;
    }
    if (origin.y<kAdsorbScope) {
        origin.y = 0;
        adsorbing = YES;
    }else if (origin.y>superSize.height - size.height - kAdsorbScope){
        origin.y = superSize.height - size.height;
        adsorbing = YES;
    }
    if (adsorbing) {
        [self setFrame:CGRectMake(origin.x, origin.y, size.width, size.height)];
        [self adsorbAnimated:YES];
    }
}

- (void)adsorbAnimated:(BOOL)animated
{
    NSAssert([self superview], @"必须先将View添加到superView上");
    CGRect frame = self.frame;
    UIView *adsorbingView = [[UIView alloc]initWithFrame: frame];
    adsorbingView.tag = kAdsorbingTag;
    [adsorbingView setBackgroundColor: [UIColor clearColor]];
    adsorbingView.clipsToBounds = YES;
    [self.superview addSubview: adsorbingView];
    
    CGSize superSize = adsorbingView.superview.frame.size;
    CGPoint center = CGPointZero;
    CGRect newFrame = frame;
    if (frame.origin.x == 0) {
        center.x = 0;
        newFrame.size.width = frame.size.width / 2;
    } else if (frame.origin.x == superSize.width - frame.size.width) {
        newFrame.size.width = frame.size.width / 2;
        newFrame.origin.x = frame.origin.x + frame.size.width / 2;
        center.x = newFrame.size.width;
    } else {
        center.x = frame.size.width / 2;
    }
    if (frame.origin.y==0) {
        center.y = 0;
        newFrame.size.height = frame.size.height / 2;
    } else if (frame.origin.y == superSize.height - frame.size.height) {
        newFrame.size.height = frame.size.height / 2;
        newFrame.origin.y = frame.origin.y + frame.size.height / 2;
        center.y = newFrame.size.height;
    } else {
        center.y = frame.size.height / 2;
    }
    [self sendToView:adsorbingView];
    [UIView animateWithDuration: animated ? kAdsorbDuration : 0 animations: ^{
        [adsorbingView setFrame: newFrame];
        [self setCenter: center];
    } completion: nil];
}

- (void)bringViewBack
{
    UIView *adsorbingView = self.superview;
    if (adsorbingView.tag == kAdsorbingTag) {
        [self sendToView: adsorbingView.superview];
        [adsorbingView removeFromSuperview];
    }
}

- (void)sendToView:(UIView *)view
{
    CGRect convertRect = [self.superview convertRect: self.frame toView: view];
    [view addSubview: self];
    [self setFrame: convertRect];
}

@end
