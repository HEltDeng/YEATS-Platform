import { config } from './config';
App({globalData:{config},onLaunch(){wx.hideShareMenu({menus:['shareAppMessage','shareTimeline']});}});
