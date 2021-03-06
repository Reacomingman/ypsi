# -*- coding: UTF-8 -*-
import codecs
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.models import User
import time,datetime
from psi import yforms
import re,csv
from settings import MEDIA_ROOT

from yforms import YLogin
from psi.models import SellOrder,Shop,Depot,Products,Customer, Staff, SellOrderDetail,Remit,InStream,InDetail,OutStream,OutDetail, Category,Posts
from django.db import connection
from django.db.models import Q,Sum
from django.utils import simplejson
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models.signals import post_save

def product_autocomplete(request):
    staff = request.user.get_profile()
    shopId = request.GET.get("shop","")
    q_str = "".join(request.GET.get('q',"").split())
    l_str = "".join(request.GET.get('limit',"").split())
    r_str = []
    pId = "".join(request.GET.get('pid',"").split())
    rId = "".join(request.GET.get('rid',"").split())
    type = "".join(request.GET.get('type',"").split())
    if pId:
        if shopId:
            staff.shop_id=shopId
        if len(OutStream.objects.filter(shop=staff.shop_id).exclude(hidden=1))>0:#当前店铺是否存在该商品出库记录
            cursor = connection.cursor()
            cursor.execute ("select oQuantity-ifNull(sQuantity,0) as nQuantity from \
            (select sum(quantity) as oQuantity,product_id as pid from PSI_OutDETAIL,psi_outStream where product_id=%s and outId_id=psi_outStream.id and psi_outstream.hidden=0 and shop_id=%s group by product_id ) \
            left join \
            (select psi_sellOrderDetail.product_id as sPid,sum(psi_sellOrderDetail.quantity) as sQuantity from psi_sellOrderDetail,psi_sellOrder where hidden=0 and oid_id=psi_sellOrder.id and shop_id=%s group by product_id) \
            on  pid=sPid order by nQuantity desc;",[pId,staff.shop_id,staff.shop_id])
            tags = cursor.fetchone()
            cursor.close()
            if tags:
                r_str2 = tags[0]
            else:
                r_str2 = 0

        else:
            r_str2 = 0
        return HttpResponse(str(r_str2))

    elif rId:
        cursor = connection.cursor()
        cursor.execute("select name,sum(ifnull(quantity,0))-ifnull(stq,0),psi_outstream.shop_id from psi_outstream,psi_outdetail,psi_shop left join "
                       "(select psi_sellorder.shop_id as ssid, sum(ifnull(quantity,0)) as stq from psi_sellorderdetail,psi_sellorder where product_id=%s and psi_sellorder.hidden=0 and oid_id=psi_sellorder.id  group by psi_sellorder.shop_id) "
                       "on psi_outstream.shop_id=ssid where  psi_outdetail.product_id=%s and psi_outstream.hidden=0 and outid_id = psi_outstream.id and psi_outstream.shop_id=psi_shop.id group by psi_outstream.shop_id",[rId,rId])
        tags = cursor.fetchall()
        cursor.close()
        for tag in tags:
            r_str.append(u"%s|%s|不明|%s\n"%(tag[0],tag[1],tag[2]))

    elif type == "mini":
        p1 = Products.objects.filter(Q (name__icontains=q_str) | Q (barcode__icontains=q_str),hidden=0)[:100]
        for p in p1:
            r_str.append("%s|%s|%s|%s|%s\n"%(p.name,p.barcode,p.p_str[1],p.id,p.p_str[2]))
            
    elif type=="simple":
        p1 = Products.objects.filter(Q (name__icontains=q_str) | Q (barcode__icontains=q_str),hidden=0)[:100]
        for p in p1:
            r_str.append("%s|%s|%s\n"%(p.name,p.barcode,p.id))

    else:
        if l_str:
            l_str = "limit "+l_str+" ;"
            q_str = "%%%s%%"%q_str
        if staff.level>4:#经理级别以下不可跨店销售
            if len(OutStream.objects.filter(shop=staff.shop_id))>0:#当前店铺是否存在该商品出库记录
                cursor = connection.cursor()
                cursor.execute ("select name,barcode,oQuantity-ifNull(sQuantity,0) as nQuantity,ifNull(price,''),pid,ifNull(size,0) from "
                "(select name,barcode,size,sum(quantity) as oQuantity,pid from PSI_OutDETAIL,psi_outStream  join "
                "(select id as pid,name,barcode,size from psi_products where name like %s or barcode like %s) on pid = product_id where outId_id=psi_outStream.id  and shop_id=%s and psi_outstream.hidden=0 group by product_id ) "
                "left join "
                "(select psi_sellOrderDetail.product_id as sPid,sum(psi_sellOrderDetail.quantity) as sQuantity,price from psi_sellOrderDetail,psi_sellOrder where hidden=0 and oid_id=psi_sellOrder.id and shop_id=%s group by psi_sellOrderDetail.product_id) "
                "on  pid=sPid order by nQuantity desc "+l_str,[q_str,q_str,staff.shop_id,staff.shop_id])
                tags = cursor.fetchall()
                cursor.close()
                for tag in tags:
                    r_str.append("%s|%s|%s|%s|%d|%s\n"%(tag[0],tag[1],tag[2],tag[3],tag[4],tag[5]))

            else:
                r_str = ("无相应出库记录||||")
        elif shopId:
            if len(OutStream.objects.filter(shop=shopId))>0:#当前店铺是否存在该商品出库记录
                cursor = connection.cursor()
                cursor.execute ("select name,barcode,pid,oQuantity-ifNull(sQuantity,0) as nQuantity from \
                            (select name,barcode,pid,sum(quantity) as oQuantity,pid from PSI_OutDETAIL,psi_outStream  join \
                            (select id as pid,name,barcode from psi_products where name like %s or barcode like %s) on pid = product_id where outId_id=psi_outStream.id and psi_outstream.hidden=0 and shop_id=%s group by product_id ) \
                            left join \
                            (select psi_sellOrderDetail.product_id as sPid,sum(psi_sellOrderDetail.quantity) as sQuantity from psi_sellOrderDetail,psi_sellOrder where hidden=0 and oid_id=psi_sellOrder.id and shop_id=%s group by psi_sellOrderDetail.product_id) \
                            on pid=sPid where nQuantity>0 order by nQuantity desc;",[q_str,q_str,shopId,shopId])
                tags = cursor.fetchall()
                cursor.close()
                for tag in tags:
                    r_str.append("%s|%s|%s|%s|0\n"%(tag[0],tag[1],tag[3],tag[2]))
        else:
            r_str = ("您并非销售人员不予查询||||")

    return HttpResponse(r_str)

def customer_search(request):
    q_str = "".join(request.GET.get('q',"").split())
    r_str = []
    cstm = Customer.objects.filter(hidden=0)
    if len(cstm)>0:
         tags = (cstm.filter(Q (name__icontains=q_str) | Q (code__icontains=q_str) | Q (telephone__icontains=q_str)))[:100]
         for tag in tags:
             r_str.append("%s\n"%tag)
    return HttpResponse(r_str)

def depot_autocomplete(request):
    q_str = "".join(request.GET.get('pid',"").split())
    r_str=[]
    depots = Depot.objects.filter(hidden=0)
    cursor = connection.cursor()
    cursor.execute ("select name,ifnull(tq,0)-ifnull(oq,0) as ttq from psi_depot left join \
    ( \
    select sum(ifnull(psi_indetail.quantity,0))as tq ,psi_indetail.depot_id as idid \
    from psi_indetail,psi_instream \
    where psi_indetail.product_id=%s and inid_id=psi_instream.id and psi_instream.hidden=0 \
    group by psi_indetail.depot_id \
    ) on psi_depot.id=idid \
    left join \
    ( \
    select sum(psi_outdetail.quantity) as oq,psi_outdetail.depot_id as odid \
    from psi_outdetail,psi_outstream \
    where psi_outdetail.product_id=%s and outid_id=psi_outstream.id and psi_outstream.hidden=0 \
    group by psi_outdetail.depot_id \
    ) on psi_depot.id=odid;",[q_str,q_str])
    tags = cursor.fetchall()
    cursor.close()
    '''
    for tag,depot in zip(tags,depots):
        r_str.append("%s|%s|%s|%s\n"%(tag[0],tag[1],depot.d_str[0],depot.id))
    return HttpResponse(r_str)
    '''
    for tag,depot in zip(tags,depots):
        r_str.append(u"%s|%s|不明|%s\n"%(tag[0],tag[1],depot.id))
    return HttpResponse(r_str)

def depot_pSum(d_id,p_id):
    cursor = connection.cursor()
    cursor.execute ("select ifnull(\
        (\
        select sum(ifnull(psi_indetail.quantity,0))-(ifnull(oq,0)) as tq from psi_indetail,psi_instream left join \
        (select sum(psi_outdetail.quantity) as oq,psi_outdetail.product_id,psi_outdetail.depot_id as odid from psi_outdetail,psi_outstream \
        where psi_outdetail.product_id=%s and psi_outdetail.depot_id=%s and outid_id=psi_outstream.id and hidden=0 group by psi_outdetail.depot_id) \
        on psi_indetail.depot_id=psi_indetail.depot_id where psi_indetail.product_id=%s and psi_indetail.depot_id=%s and inid_id=psi_instream.id and hidden=0  group by psi_indetail.depot_id \
        ),0) as tq ",[p_id,d_id,p_id,d_id])
    tq = cursor.fetchone()[0]
    return tq

def ypsi_staff_list(request):
    shopId = get_object_or_404(Shop, id=request.user.get_profile().shop_id)
    q_str = "".join(request.GET.get('q',"").split())
    r_str = []
    tags = Staff.objects.filter(shop=shopId).exclude(level=0).filter(name__icontains=q_str)
    for tag in tags:
        r_str.append("%s|%s\n"%(tag,tag.id))
    return HttpResponse(r_str)

def user_login(request):
    request.session.set_expiry(0) #关闭浏览器session失效
    act = request.GET.get("act","")
    err_count = request.session.get("err_count",0)
    page_title = "YPSI 系统登录"
    if err_count>5 and act!="stop":
        return HttpResponseRedirect('?act=stop')
    if act == "check":
        if request.method == 'POST':
            form=YLogin(request.POST.copy())
            if form.is_valid():
                form = form.cleaned_data
                name = form['username']
                pwd = form['password']
                user = authenticate(username=name, password=pwd)
                if user is not None:
                    # 转到成功页面
                    login(request, user)
                    #request.session["userid"] = user.id 与session["_auth_user_id"]重复
                    #request.session["username"] = user.get_profile().name
                    #request.session["level"] = user.get_profile().level
                    next_path = request.session.get("next_path","")
                    if len(next_path) < 1:
                        next_path = "/"
                    return HttpResponseRedirect('%s'%next_path)
                else:
                    #request.session["login_count"] +=1
                    err_count += 1
                    request.session["err_count"] = err_count
                    return HttpResponseRedirect('?act=err')

            else:
                page_title="表单填写错误"

    elif act == "logout":
        logout(request)
        request.session.flush()
        return HttpResponseRedirect('/accounts/login/?act=out')
    elif act == "stop":
        page_title = "错误次数过多"
        form = ""
    else:
        if act == "out":
            page_title = "原登录信息已注销，可重新登录"
        elif act == "err":
            page_title="用户名或密码错误"
        form = YLogin()
        request.session["next_path"] = request.GET.get("next","")
    return render_to_response('accounts/login.html',locals())

@login_required
def ypsi_index(request):
    request.session.set_expiry(0) #关闭浏览器session失效
    user = request.user.get_profile()
    last_login = request.user.last_login
    act = request.GET.get("act","")
    wmode = request.GET.get("w","")
    page_errs=""
    #date_list(12)#读取指定时间段
    days = request.GET.get('days',7)
    try:
        days = int(days)
    except :
        page_errs=("请输入正确参数")
    if user.level > 5 and wmode <> "1" and days > 60 :
        page_errs=("普通模式下可统计天数上限为60日 <a href='?w=1&days=120'><span><img src='/static/images/css/chart16.png'/> 切换宽屏模式查看更多</span></a> 或 <a href='javascript:history.go(-1)'>返回上一页</a>")
    elif user.level > 5 and wmode == "1" and days > 120 :
        page_errs=("店长以下级别人员可统计天数上限为120日")
    if page_errs == "":
        dlist = ypsi_sell_list(days)[0]
        s_str=ypsi_sell_list(days)[1]
        page_title = u"首页"
        plist = Posts.objects.filter(hidden=0).order_by("-id")
        slist = SellOrder.objects.filter(hidden=0).order_by("-id")[:10]
        if act == "getData":
            jStr = {"plist":[],"slist":[],"err":page_errs}
            for p in plist:
                jStr["plist"].append({"title":p.title,"note":p.note,"date":datetime.datetime.strftime(p.date,'%Y-%m-%d')})
            for s in slist:
                jStr["slist"].append({"sid":s.id,"shop":s.shop.name,"staff":s.staff.name,"amount":s.total,"date":datetime.datetime.strftime(s.date,'%Y-%m-%d %H:%M:%S')})
            return HttpResponse(simplejson.dumps({"page_title":page_title,"plist":jStr["plist"],"slist":jStr["slist"],"dlist":dlist,"s_str":s_str},ensure_ascii=False), mimetype="text/plain")
        else:
            return render_to_response("app/index.html",{"page_title":page_title,"err":page_errs,"user":user,"last_login":last_login,"plist":plist,"slist":slist,"dlist":dlist,"s_str":s_str,"wmode":wmode})
    else:
        return HttpResponse("<html><center>%s</center></html>"%page_errs)
    
@login_required
def ypsi_sales(request):
    page_title = '新增订单 - 销售管理'
    return render_to_response('app/sales.html',{"page_title":page_title,"level":request.user.get_profile().level})

def ypsi_sell_list(ds):
    if isinstance(ds,int):
        today = datetime.datetime.now()
        pastday = (today - datetime.timedelta(days=ds)).strftime("%Y-%m-%d")
        date_list = []
        for day in range(1,ds+1):
            d1 = today-datetime.timedelta(days=(ds-day))#省略了pastday
            date_list.append(d1.strftime("%m-%d"))
        shop_list = Shop.objects.exclude(name='总部').values('id','name').order_by('id')
        #shop_list2 = shop_list.values_list('name', flat=True).order_by('id')
        s_str=[]
        if len(SellOrder.objects.all())>0:#避免空数据错误
            cursor = connection.cursor()
            for index,shop in enumerate(shop_list):
                s_str.append({'name':shop['name'],'data':[]})
                cursor.execute("select sum(quantity*price)-td as tamount,date(date) as sdate2 from psi_sellorderdetail,psi_sellorder left join  "
                                "(select sum(psi_sellorder.discount) as td,date(date) as sdate,psi_sellorder.id as sellid from psi_sellorder where psi_sellorder.hidden=0 and shop_id=%s group by sdate having sdate>%s) "
                                "on sellid=psi_sellorder.id  where psi_sellorder.hidden=0 and psi_sellorder.id=oid_id and shop_id=%s group by sdate2 having sdate2>%s;",[shop['id'],pastday,shop['id'],pastday])
                sss = cursor.fetchall()
                day_list = [0]*ds #简化循环,以日期跨度初始化列表
                for ss in sss:
                    day_df = (datetime.datetime.strptime(ss[1],"%Y-%m-%d")-today).days #计算日期差,作为列表索引使用
                    day_list[day_df]=round(ss[0],2) #赋值
                s_str[index]['data']=day_list
            cursor.close()
            del shop_list,cursor,today
        return date_list,simplejson.dumps(s_str,ensure_ascii=False)#转JSON数据避免中文解码问题

def ypsi_sales_search(request):
    if request.method == "POST":
        flag = False
        eArr = []
        rows = 0
        t_total = 0
        oStr = eval(request.raw_post_data)
        level = request.user.get_profile().level
        shop_id = oStr.get("shop","")
        if shop_id  == "0": #shop_input优先传递shop筛选值
            ShopId = "0"
        elif shop_id:
            ShopId = get_object_or_404(Shop, id=oStr["shop"])
        else:
            ShopId = get_object_or_404(Shop, id=request.user.get_profile().shop_id)

        if oStr["type"] is "all" or ShopId == "0":
            oQ = SellOrder.objects.all().order_by('-id')
        else:
            oQ = SellOrder.objects.filter(shop=ShopId).order_by('-id')

        if oStr["type"] is "simple":
            if ShopId == "0" or level < 5:
                oQ = SellOrder.objects.all().order_by('-id')[:oStr["count"]]
            else:
                oQ = SellOrder.objects.filter(shop=ShopId).order_by('-id')[:oStr["count"]]
            flag = True

        elif oStr["type"] is "exact":
            oQ = SellOrder.objects.filter(id=oStr["count"],hidden=0)
            flag = True
            rows = len(oQ)
        else:
            Reg = re.match(ur"^[A-Za-z0-9]{0,20}$",oStr["code"])
            if Reg is None:
                eArr.append("订单编号应由4位以上字母及数字组成")
            else:
                oQ = oQ.filter(code__icontains=oStr["code"])

            if oStr["customer"]:
                if re.match(ur"^[1-9][0-9]*$",oStr["customer"]):
                    oQ = oQ.filter(customer=(get_object_or_404(Customer, id=oStr["customer"])))
                else:
                    eArr.append("顾客查询参数错误")


            if oStr["staff"]:
                if re.match(ur"^[1-9][0-9]*$",oStr["staff"]):
                    oQ = oQ.filter(staff=oStr["staff"])
                else:
                    eArr.append("销售人员查询参数错误")

            if oStr["hidden"] is "true":
                oQ = oQ.filter(hidden=True)
            else:
                oQ = oQ.filter(hidden=False)

            if len(oStr["note"])>100:
                eArr.append("备注查询字段应少于100字符")
            else:
                oQ = oQ.filter(note__icontains=oStr["note"])

            if oStr["sDate"]:
                if time.strptime(oStr["sDate"], "%Y-%m-%d"):
                    sDate = time.strptime(oStr["sDate"], "%Y-%m-%d")
                    if level > 5 and datetime.datetime.now() - datetime.timedelta(days=93)>datetime.datetime(*sDate[:6]):
                        eArr.append("店长以下级别人员只可回溯3个月内订单")
                    else:
                        oQ = oQ.filter(date__gte=datetime.datetime(*sDate[:6]))
                else:
                     eArr.append("日期请按照 2011-12-30 的格式填写")
            else:
                oQ = oQ.filter(date__gte=(datetime.datetime.now()-datetime.timedelta(days=92)))

            if oStr["eDate"]:
                if time.strptime(oStr["eDate"], "%Y-%m-%d"):
                    sDate = time.strptime(oStr["eDate"], "%Y-%m-%d")
                    if time.localtime() < sDate:
                        eArr.append("结束时间不能大于当前日期")
                    else:
                        oQ = oQ.filter(date__lte=datetime.datetime(*sDate[:6])+datetime.timedelta(days=1))
                else:
                     eArr.append("日期请按照 2011-12-30 的格式填写")
            else:
                oQ = oQ.filter(date__lte=(datetime.datetime.now()+datetime.timedelta(days=1)))

            '''
            if oStr["lMoney"]:
                Reg = re.match(ur"^[0-9]+(.[0-9]{2}|.[0-9]{1})?$",oStr["lMoney"])
                if Reg is None:
                    eArr.append("请正确录入起始金额")
                else:
                    oQ = oQ.filter(date__lt=(datetime.datetime.now()))
            if oStr["mMoney"]:
                Reg = re.match(ur"^[0-9]+(.[0-9]{2}|.[0-9]{1})?$",oStr["mMoney"])
                if Reg is None:
                    eArr.append("请正确录入金额上限")
            '''

            if len(eArr)<1 and len(oStr["sDate"])>0 and len(oStr["eDate"])>0:
                if time.strptime(oStr["eDate"], "%Y-%m-%d")<time.strptime(oStr["sDate"], "%Y-%m-%d"):
                    eArr.append("起始时间不能够大于结束时间")
                #print eArr
                #print connection.queries
                #time.sleep(3)

        if len(eArr)<1:
            rows = len(oQ)
            if rows>0:
                mP = (int(oStr["page"])-1)*20
                oQ2 = oQ[mP:mP+20]
                flag = True
                for o in oQ2:
                    if o.customer:
                        ctm = o.customer.name
                        cti = o.customer_id
                    else:
                        ctm =u"未登记"
                        cti = 0
                    eArr.append({"id":o.id,"code":o.code,"total":o.total,"discount":str(o.discount), "date":o.date.strftime("%Y-%m-%d"),"customer":ctm,"customer_id":cti,"staff":o.staff.name,"staff_id":o.staff_id,"note":o.note,"hidden":o.hidden})
                for o in oQ:
                    t_total += o.total

                if oStr.get("explort","") == "true":
                    i = 1
                    d_total = 0
                    csvfile = open('%s/csv/result%s.csv'%(MEDIA_ROOT,request.user.get_profile().shop_id),'wb')
                    csvfile.write(codecs.BOM_UTF8)
                    w = csv.writer(csvfile)
                    w.writerow(["编号","店铺","日期","产品名称","尺寸","类别","价格","数量","小计"])
                    for o in oQ.order_by("date"):
                        odQ = SellOrderDetail.objects.filter(oid=o.id)
                        for od in odQ:
                            w.writerow([i,o.shop.name.encode('utf8'), o.date, od.product.name.encode('utf8'),od.product.size,od.product.category.name.encode('utf8'),od.price,od.quantity,od.price*od.quantity])
                            i += 1
                        d_total += o.discount
                    w.writerow(["","","","","","折扣总额",d_total,"实收",t_total])
                    csvfile.close()

            else:
                eArr.append("无匹配记录")
    else:
        return render_to_response("app/sales_show.html",{"page_title":"订单详情"})
    return HttpResponse(simplejson.dumps({"flag":flag,"level":level,"rows":rows,"data":eArr,"oStr":oStr,"t_total":t_total,"type":oStr["type"]},ensure_ascii=False), mimetype="text/plain")

'''
def ypsi_sales_explort(request):
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename="somefilename.csv"'
    writer = csv.writer(response)
    writer.writerow(['First row', 'Foo', 'Bar', 'Baz'])
    writer.writerow(['Second row', 'A', 'B', 'C', '"Testing"', "Here's a quote"])
    return response
'''

def ypsi_sales_add(request):
    if request.method == "POST":
        oStr = eval(request.raw_post_data)
        shopId = get_object_or_404(Shop, id=request.user.get_profile().shop_id)
        staffId= get_object_or_404(Staff, id=request.user.get_profile().id)
        sId= "".join(oStr['id'].split())
        sHidden = "".join(oStr['hidden'].split())
        sCode = "".join(oStr['code'].split())
        sDiscount = "".join(oStr['discount'].split())
        sNote = "".join(oStr['note'].split())
        sDate = oStr.get("date","")
        flag = True
        msg = ""
        #print oStr

        if sId :
            if re.match(ur"^[1-9][0-9]*$",sId) is None:
                flag = False
                msg = "订单ID参数错误,请修正后重新提交"
            else:
                newSellOrder = get_object_or_404(SellOrder, id=sId)
                if sHidden is "1":
                    newSellOrder.hidden = True
                    msg = u"订单 (id:%d 单据号:%s) 删除操作成功"%(newSellOrder.id,newSellOrder.code)
                    newSellOrder.save()
                else:

                    if sCode:
                        regC = re.match(ur"^[A-Za-z0-9]{4,20}$",sCode)
                        if regC is None:
                            flag = False
                            msg = "订单编号应由4位以上字母及数字组成"
                    if sDiscount:
                        regD = re.match(ur"^\d+\.?\d{0,2}$",sDiscount)
                        #regD = re.match(ur"^(([0-9]+\.[0-9]{2})|([0-9]*[1-9][0-9]*))$",sDiscount)
                        if regD is None:
                            flag = False
                            msg = "折扣金额错误,请修正后重新提交"
                    if len(sNote) > 100:
                        flag = False
                        msg = "备注过长,请控制在100字符以内"
                    if sDate:
                        regDT = re.match(ur"^((((1[6-9]|[2-9]\d)\d{2})-(0?[13578]|1[02])-(0?[1-9]|[12]\d|3[01]))|(((1[6-9]|[2-9]\d)\d{2})-(0?[13456789]|1[012])-(0?[1-9]|[12]\d|30))|(((1[6-9]|[2-9]\d)\d{2})-0?2-(0?[1-9]|1\d|2[0-8]))|(((1[6-9]|[2-9]\d)(0[48]|[2468][048]|[13579][26])|((16|[2468][048]|[3579][26])00))-0?2-29-)) (20|21|22|23|[0-1]?\d):[0-5]?\d:[0-5]?\d$",sDate)
                        if regDT is None:
                            flag = False
                            msg = "请按照2012-01-01 08:30:00格式填写日期"
                        else:
                            t1= time.strptime(sDate,"%Y-%m-%d %H:%M:%S")
                            if t1 > time.localtime():
                                flag = False
                                msg = "销售时间不能在今日之后"
                    idArr = []
                    for i,od in enumerate(oStr['orderDetail']):
                        regP = re.match(ur"^\d+\.?\d{0,2}$",od['price'])
                        if regP is None:
                            flag = False
                            msg = "订单第%s项产品价格错误,请修正后重新提交"%(i+1)
                            break
                        regQ = re.match(ur"^[1-9][0-9]*$",od['quantity'])
                        if regQ is None:
                            flag = False
                            msg = "订单第%s项产品数量错误,请修正后重新提交"%(i+1)
                            break

                    if flag:
                        for i,od in enumerate(oStr['orderDetail']):
                            productId = get_object_or_404(Products, id=od['product'])
                            if od['id']:
                                SellOrderDetail.objects.filter(id=int(od['id'])).update(price=od['price'],quantity=od['quantity'])
                                idArr.append(od['id'])
                            else:
                                newOD = SellOrderDetail(oid=newSellOrder,product=productId,price=od['price'],quantity=od['quantity'])
                                newOD.save()
                                idArr.append(newOD.id)

                        SellOrderDetail.objects.filter(oid=newSellOrder).exclude(id__in=idArr).delete()
                        SellOrder.objects.filter(id=sId).update(code=oStr['code'],discount=oStr['discount'],date=sDate,note=oStr['note'],hidden=False)
                        msg = u"订单 (id:%d 单据号:%s) 更新成功"%(newSellOrder.id,newSellOrder.code)

        else:
            if sCode:
                regC = re.match(ur"^[A-Za-z0-9]{4,20}$",sCode)
                if regC is None:
                    flag = False
                    msg = "订单编号应由4位以上字母及数字组成"
            if sDiscount:
                regD = re.match(ur"^\d+\.?\d{0,2}$",sDiscount)
                if regD is None:
                    flag = False
                    msg = "折扣金额错误,请修正后重新提交"
            if len(sNote) > 100:
                flag = False
                msg = "备注过长,请控制在100字符以内"


            if flag:
                newSellOrder = SellOrder(shop=shopId,staff=staffId,code=oStr['code'],discount=oStr['discount'],note=oStr['note'],date=datetime.datetime.strftime(datetime.datetime.now(),'%Y-%m-%d %H:%M:%S'))
                if len("".join(oStr['customer'].split()))>0:
                    customerId = get_object_or_404(Customer,id="".join(oStr['customer'].split()))
                    newSellOrder = SellOrder(shop=shopId,staff=staffId,customer=customerId,code=oStr['code'],discount=oStr['discount'],note=oStr['note'],date=datetime.datetime.strftime(datetime.datetime.now(),'%Y-%m-%d %H:%M:%S'))
                newSellOrder.save()
                for i,od in enumerate(oStr['orderDetail']):
                    regP = re.match(ur"^\d+\.?\d{0,2}$",od['price'])
                    if regP is None:
                        flag = False
                        msg = "订单第%s项产品价格错误,请修正后重新提交"%(i+1)
                        break

                    regQ = re.match(ur"^[1-9][0-9]*$",od['quantity'])
                    if regQ is None:
                        flag = False
                        msg = "订单第%s项产品数量错误,请修正后重新提交"%(i+1)
                        break

                    cursor = connection.cursor()
                    productId = get_object_or_404(Products, id=od['product'])
                    if len(OutStream.objects.filter(shop=shopId).exclude(hidden=1))>0:#当前店铺是否存在出库记录
                        cursor.execute ("select oQuantity-ifNull(sQuantity,0) as nQuantity from \
                        (select sum(quantity) as oQuantity,pid from PSI_OutDETAIL,psi_outStream  join \
                        (select id as pid from psi_products) on pid = product_id where pid=%s and outId_id=psi_outStream.id and psi_outstream.hidden=0 and shop_id=%s group by product_id ) \
                        left join \
                        (select psi_sellOrderDetail.product_id as sPid,sum(psi_sellOrderDetail.quantity) as sQuantity from psi_sellOrderDetail,psi_sellOrder where hidden=0 and oid_id=psi_sellOrder.id and shop_id=%s group by psi_sellOrderDetail.product_id) \
                        on  pid=sPid order by nQuantity desc;",[productId.id,shopId.id,shopId.id])
                        tags = cursor.fetchone()
                        cursor.close()
                        if tags:
                            pq = tags[0]
                        else:
                            pq = 0
                    else:
                        pq = 0
                    if int(od['quantity']) > pq:
                        flag = False
                        msg = u"%s 数量超出库存，请返回销售页面刷新重试"%productId.name
                        break

                    if flag:
                        SellOrderDetail(oid=newSellOrder,product=productId,price=od['price'],quantity=od['quantity']).save()
                if flag is False:
                    #SellOrderDetail.objects.filter(oid=newSellOrder).delete()
                    SellOrder.objects.filter(id=newSellOrder.id).delete()
        return HttpResponse(simplejson.dumps({"flag":flag,"data":msg},ensure_ascii=False), mimetype="text/plain")

def ypsi_sales_show(request):
    qStr = request.GET.get('q',"")
    s_list = Shop.objects.exclude(name="总部").only("id","name")
    if len(qStr)<1:
        page_title = "订单查询 / 修改"
        #shopId = get_object_or_404(Shop, id=request.user.get_profile().shop_id)
        return render_to_response('app/sales_show.html',{"page_title":page_title,"shop_id":request.user.get_profile().shop.id,"s_list":s_list,"level":request.user.get_profile().level})
    else:
        flag = True
        data = []
        if re.match(ur"^[1-9][0-9]*$",qStr) is None:
            flag = False
            data.append("查询参数错误")
        else:
            #shopId = get_object_or_404(Shop, id=request.user.get_profile().shop_id)
            #order = SellOrder.objects.get(id=qStr,shop=shopId)
            order = SellOrder.objects.get(id=qStr)
            ods = SellOrderDetail.objects.filter(oid=order)
            for od in ods:
                data.append({"pname":od.product.name,"pid":od.product_id,"psize":od.product.size,"price":str(od.price),"quantity":od.quantity})
            #ods = SellOrder.objects.get(id=qStr).sellorderdetail_set.all()
            #print order.id
        #time.sleep(1)
        return HttpResponse(simplejson.dumps({"flag":flag,"data":data,"discount":str(order.discount),"note":order.note},ensure_ascii=False), mimetype="text/plain")

def ypsi_sales_mini(request):
    eArr = []
    flag = False
    data =[]
    level = request.user.get_profile().level
    if level>5 or level==3: #权限排除
        eArr.append("Please check permissions ! 订单修改需店长以上权限")
    else:
        if request.method == "GET":
            qStr = request.GET.get('q',"0")
            if re.match(ur"^[1-9][0-9]*$",qStr) is None:
                eArr.append("查询参数错误")
            else:
                shopId = get_object_or_404(Shop, id=request.user.get_profile().shop_id)
                order = get_object_or_404(SellOrder,id=qStr,shop=shopId)
                ods = SellOrderDetail.objects.filter(oid=order)
                '''
                if order.customer:
                    ctm = order.customer.name+""+order.customer.code
                    cti = order.customer.id
                else:
                    ctm =u"未登记"
                    cti = 0
                for od in ods:
                    #print od.product.name
                    data.append({"pname":od.product.name,"pid":od.product_id,"psize":od.product.size,"price":str(od.price),"quantity":od.quantity})

                    return HttpResponse(simplejson.dumps({"flag":flag,"total":order.total,"staff":order.staff.name,"staff_id":order.staff_id,
                                                          "customer":ctm,"customer_id":cti,
                                                          "discount":order.discount,"note":order.note,"data":data},ensure_ascii=False), mimetype="text/plain")
                    '''
                return render_to_response('app/sales_edit_mini.html',locals())

    if len(eArr)>0:
        data = eArr
        flag = False
    return HttpResponse(simplejson.dumps({"flag":flag,"data":data},ensure_ascii=False), mimetype="text/plain")

def ypsi_sales_chart(request):
    #page_title = '销售统计 - 销售管理'
    return HttpResponse("Just Wait a moument ...", mimetype="text/plain")

@login_required()
def ypsi_depots(request):#查询店铺库存时产品 当前店铺库存项目 循环不合理，待修正
    page_title = "库存状况概览"
    act = request.GET.get("act","")
    qid = request.GET.get("id","")
    level = request.user.get_profile().level
    p_list = ""
    pd_list = ""
    st_list = ""
    page_range = ""
    if act:
        sdp_list = []
        stq_list = []
        cursor = connection.cursor()
        if (act == "shop" or act == "explort") and qid:
            shop = get_object_or_404(Shop,id=qid)
            page_title = u"%s 当前库存产品一览"%shop.name
            cursor.execute("select psi_outdetail.product_id,(sum(quantity)-ifnull(sq,0)) as tq from psi_outdetail,psi_outstream left join "
                            "(select product_id as spid,shop_id as ssid, sum(quantity) as sq from psi_sellorder,psi_sellorderdetail where psi_sellorder.hidden=0 and oid_id = psi_sellorder.id and ssid=%s group by spid) "
                            "on psi_outdetail.product_id=spid where psi_outstream.hidden=0 and psi_outstream.shop_id=%s and psi_outstream.id = outid_id  group by psi_outdetail.product_id order by product_id desc",[qid,qid])


        elif act == "depot" and qid and level<5:
            depot = get_object_or_404(Depot,id=qid)
            page_title = u"%s 当前库存产品一览"%depot.name
            cursor.execute("select psi_indetail.product_id,(sum(quantity)-ifnull(sq,0)) as tq from psi_indetail,psi_instream left join "
                            "(select product_id as spid,depot_id as odid, sum(quantity) as sq from psi_outstream,psi_outdetail where psi_outstream.hidden=0 and outid_id = psi_outstream.id and odid=%s group by spid) "
                            "on psi_indetail.product_id=spid  where psi_instream.hidden=0 and psi_indetail.depot_id=%s and psi_instream.id = inid_id  group by psi_indetail.product_id order by product_id desc",[qid,qid])

        sdp = cursor.fetchall()
        cursor.close()
        for s in sdp:
            sdp_list.append(s[0])
            stq_list.append(s[1])
        p_list = Products.objects.filter(hidden=0,id__in=sdp_list).order_by("-id")

        if request.GET.get("explort","") == "true":
            response = HttpResponse(mimetype="text/csv")
            #response.write(codecs.BOM_UTF8)
            response.write("\xEF\xBB\xBF")
            response["Content-Disposition"] = "attachment; filename=库存统计表.csv"
            writer = csv.writer(response)
            #writer.writerow([u"名称".encode("GBK"),u"条码".encode("GBK"),u"尺寸".encode("GBK"),u"当前库存".encode("GBK"),u"各仓库总库存".encode("GBK"),u"状态".encode("GBK")])
            writer.writerow(["编号","名称","条码","尺寸","当前库存","仓库总库存","状态"])
            i = 1
            for p,s in zip(p_list,stq_list):
                i += 1
                if p.hidden == 1:
                    pStatus = u"已删除"
                else:
                    pStatus = u"正常"
                writer.writerow([i,p.name.encode('utf8'),p.barcode,p.size,s,p.p_str[1],pStatus.encode('utf8')])
            return response

        paginator = Paginator(p_list, 20)
        after_range_num = 5
        befor_range_num = 4
        try:
            page = int(request.GET.get("page",1))
            if page < 1:
                page = 1
        except ValueError:
            page = 1
        st_list = stq_list[20*(page-1):(20*page)] #当前容器库存数
        pd_list = paginator.page(page)
        if page >= after_range_num:
            page_range = paginator.page_range[page-after_range_num:page+befor_range_num]
        else:
            page_range = paginator.page_range[0:int(page)+befor_range_num]


    s_list = Shop.objects.exclude(name="总部").only("id","name")
    d_list = Depot.objects.filter(hidden=0).only("id","name")

    return render_to_response('app/depots.html',{"page_title":page_title,"s_list":s_list,"d_list":d_list,"p_list":p_list,"level":level,"r_list":pd_list,"st_list":st_list,"url":"?act=%s&id=%s"%(act,qid),"qid":qid,"page_range":page_range,"rows":len(p_list)})

def ypsi_depots_charts(request):
    qStr = request.GET.get("type","")
    pid = request.GET.get("id","")
    sid = request.GET.get("shop","")
    if qStr:
        cursor = connection.cursor()
        if qStr == "depots":
            cursor.execute("select name,(sum(ifnull(quantity,0))-ifnull(otq,0)) as tq from psi_indetail,psi_depot,psi_instream left join "
                       "(select product_id as opid,sum(ifnull(quantity,0)) as otq,depot_id as odid from psi_outdetail,psi_outstream where outid_id=psi_outstream.id and psi_outstream.hidden=0 group by depot_id) "
                       "on psi_indetail.depot_id=odid where psi_depot.id=psi_indetail.depot_id and psi_instream.id=psi_indetail.inid_id and psi_instream.hidden=0 group by depot_id ;")
        elif qStr == "shops":
            cursor.execute("select name,(sum(quantity)-ifnull(sq,0)) as tq from psi_outdetail,psi_outstream,psi_shop left join "
                           "(select psi_sellorder.shop_id as ssid, sum(quantity) as sq from psi_sellorder,psi_sellorderdetail where psi_sellorder.hidden=0 and oid_id = psi_sellorder.id group by shop_id) "
                           "on psi_outstream.shop_id=ssid where psi_outstream.hidden=0 and psi_outstream.id = outid_id and psi_outstream.shop_id=psi_shop.id group by shop_id  ;")
        elif qStr == "pdp" and pid:
            cursor.execute ("select name,ifnull(tq,0)-ifnull(oq,0) as ttq from psi_depot left join \
                            ( \
                            select sum(ifnull(psi_indetail.quantity,0))as tq ,psi_indetail.depot_id as idid \
                            from psi_indetail,psi_instream \
                            where psi_indetail.product_id=%s and inid_id=psi_instream.id and psi_instream.hidden=0 \
                            group by psi_indetail.depot_id \
                            ) on psi_depot.id=idid \
                            left join \
                            ( \
                            select sum(psi_outdetail.quantity) as oq,psi_outdetail.depot_id as odid \
                            from psi_outdetail,psi_outstream \
                            where psi_outdetail.product_id=%s and outid_id=psi_outstream.id and psi_outstream.hidden=0 \
                            group by psi_outdetail.depot_id \
                            ) on psi_depot.id=odid;",[pid,pid])
        elif qStr == "psp" and pid:
            cursor.execute("select name,sum(ifnull(quantity,0))-ifnull(stq,0) from psi_outstream,psi_outdetail,psi_shop left join "
                           "(select psi_sellorder.shop_id as ssid, sum(ifnull(quantity,0)) as stq from psi_sellorderdetail,psi_sellorder where product_id=%s and psi_sellorder.hidden=0 and oid_id=psi_sellorder.id  group by psi_sellorder.shop_id) "
                           "on psi_outstream.shop_id=ssid where  psi_outdetail.product_id=%s and psi_outstream.hidden=0 and outid_id = psi_outstream.id and psi_outstream.shop_id=psi_shop.id group by psi_outstream.shop_id",[pid,pid])
        elif qStr == "pssp" and pid:
            if sid == "0":
                cursor.execute("select date(date) as sdate,sum(quantity) from psi_sellorder,psi_sellorderdetail where psi_sellorder.id = psi_sellorderdetail.oid_id and product_id=%s and hidden=0 group by sdate",[pid])
            else:
                cursor.execute("select date(date) as sdate,sum(quantity) from psi_sellorder,psi_sellorderdetail where psi_sellorder.shop_id=%s and psi_sellorder.id = psi_sellorderdetail.oid_id and product_id=%s and hidden=0 group by sdate",[sid,pid])
        r_str = cursor.fetchall()
        cursor.close()
        data = []
        #dlist = []
        ttq=0
        for index,r in enumerate(r_str):
            if r[1] <> 0:
                data.append([r[0],r[1]])
                ttq +=r[1]
        return HttpResponse(simplejson.dumps({"data":data,"ttq":ttq},ensure_ascii=False), mimetype="text/plain")


def ypsi_depots_product(request):
    page_title = "产品细目查询"
    pid = request.GET.get("id","")
    sid = request.GET.get("sid","0")
    s_list = Shop.objects.exclude(name="总部").only("id","name")
    if pid:
        pd = Products.objects.get(id=pid)
        if sid == "0":
            tq = SellOrderDetail.objects.filter(product=pd,oid__in=SellOrder.objects.filter(hidden=0).only(id)).aggregate(Sum('quantity'))['quantity__sum']
        else:
            tq = SellOrderDetail.objects.filter(product=pd,oid__in=SellOrder.objects.filter(hidden=0,shop=get_object_or_404(Shop, id=sid)).only(id)).aggregate(Sum('quantity'))['quantity__sum']
        if tq is None or tq == "":
            tq = 0
        return render_to_response('app/depots_product.html',{"page_title":page_title,"s_list":s_list,"sid":sid,"level":request.user.get_profile().level,"pd":pd,"tq":tq})
    else:
        return render_to_response('app/depots_product.html',{"page_title":page_title,"s_list":s_list,"sid":0,"level":request.user.get_profile().level})

def ypsi_depots_in(request):
    act = request.GET.get("act","list")
    iId = request.GET.get("id","")
    pname = ""
    level = request.user.get_profile().level
    page_title = "入库单列表"
    if act == "add":
        page_title = "新增入库提要信息"
        if request.POST:
            form = yforms.InStream(request.POST)
            if form.is_valid():
                fc = form.cleaned_data
                InStream(code=fc["code"],supplier=fc["supplier"],date=fc["date"],keeper=fc["keeper"],staff1=fc["staff1"],note=fc["note"]).save()
                return HttpResponseRedirect("?act=added")

        else:
            form = yforms.InStream()
        return render_to_response('app/depots_instream.html',{"page_title":page_title,"form":form,"act":act})

    elif act == "edit":
        page_title = "修改入库提要信息"
        ins = get_object_or_404(InStream, id=iId)
        user = request.user.get_profile().id
        if request.POST:
            form = yforms.InStream(request.POST)
            if form.is_valid():
                fc = form.cleaned_data
                if (ins.code<>fc["code"]) or (ins.supplier<>fc["supplier"]) or (ins.date<>fc["date"]) or (ins.keeper<>fc["keeper"]) or (ins.staff1<>fc["staff1"]) or (ins.hidden<>fc["hidden"]) or (ins.note<>fc["note"]) :
                    ins.code=fc["code"]
                    ins.supplier=fc["supplier"]
                    ins.date=fc["date"]
                    ins.keeper=fc["keeper"]
                    ins.staff1=fc["staff1"]
                    ins.hidden=fc["hidden"]
                    ins.note=fc["note"]
                    ins.save()
                return HttpResponseRedirect("?act=edited")
            
        else:
            form = yforms.InStream({"code":ins.code,"supplier":ins.supplier,"date":ins.date,"keeper":user,"staff1":ins.staff1_id,"hidden":ins.hidden,"note":ins.note,"log":ins.log})
        return render_to_response('app/depots_instream.html',{"page_title":page_title,"form":form,"act":"edit","iId":iId})

    elif act == "del":
        msg = "fail"
        if request.method == "POST":
            instream = get_object_or_404(InStream, id=request.POST.get("id",""))
            instream.hidden = True
            instream.save()
            msg = "success"
        return HttpResponse(msg, mimetype="text/plain")


    elif act == "d_add":
        product = get_object_or_404(Products, id=request.POST.get("pid",""))
        depot = get_object_or_404(Depot, id=request.POST.get("depot",""))
        ins = get_object_or_404(InStream, id=request.POST.get("insid",""))
        note = request.POST.get("note","")
        value = request.POST.get("value","")
        quantity = request.POST.get("quantity","")
        
        msg = []
        flag = True
        idid = ""
        regV = re.match(ur"^\d+\.?\d{0,2}$",value)
        if regV is None:
            flag = False
            msg.append("产品价格错误")
        regQ = re.match(ur"^[1-9][0-9]*$",quantity)
        if regQ is None:
            flag = False
            msg.append("产品数量错误")
        if len(note)>100:
            flag = False
            msg.append("位置详细信息超过100字符")
        if flag:
            ind = InDetail(inid=ins,product=product,value=value,quantity=quantity,depot=depot,depotdetail=note)
            ind.save()
            idid = ind.id
        return HttpResponse(simplejson.dumps({"flag":flag,"id":idid,"msg":"</br>".join(msg)},ensure_ascii=False), mimetype="text/plain")
        
        
    elif act=="d_del":
        idId = request.POST.get("id","")
        ind = get_object_or_404(InDetail, id=idId)
        flag = True
        if ind.product.p_str[3] - ind.quantity >ind.product.p_str[4]:
            ins = ind.inid
            if ins.log is None:
        	    ins.log = ""
            ins.log = u"%s %s 删除 产品：%s\n原:%s套 单价%s 仓库%s\n%s\n"\
            %(datetime.date.today(),request.user.get_profile().name,ind.product.name,ind.quantity,ind.value,ind.depot.name,31*'-') + ins.log
            ins.save()
            ind.delete()
        else:
            flag = False
        return HttpResponse(flag, mimetype="text/plain")
    elif act =="d_edit":
        idId = request.POST.get("id","")
        ind = get_object_or_404(InDetail, id=idId)
        depot = get_object_or_404(Depot,id=request.POST.get("depot",""))
        msg = []
        flag = True
        value = request.POST.get("value","")
        quantity = request.POST.get("quantity","")
        depotdetail = request.POST.get("depotdetail","")
        regV = re.match(ur"^\d+\.?\d{0,2}$",value)
        if regV is None:
            flag = False
            msg.append("产品价格错误")
        regQ = re.match(ur"^[1-9][0-9]*$",quantity)
        if regQ is None:
            flag = False
            msg.append("产品数量错误")
        if flag:
            if ind.quantity-int(quantity) > ind.product.p_str[1]:
                flag=False
                msg.append("修改后入库总数不可小于出库总数")
            d_in = InDetail.objects.filter(product=ind.product,depot=depot,inid__in=InStream.objects.filter(hidden=0)).aggregate(Sum('quantity'))["quantity__sum"]
            d_out = OutDetail.objects.filter(product=ind.product,depot=depot,outid__in=OutStream.objects.filter(hidden=0)).aggregate(Sum('quantity'))['quantity__sum']
            if d_out is None:
                d_out = 0
            if d_in is None:
                d_in = 0
            if (ind.quantity-int(quantity)) > (d_in-d_out):
                flag=False
                msg.append("修改后当前仓库入库总数不可小于出库总数,最大可修改值为%s"%(ind.quantity-(d_in-d_out)))

        if flag:
            if (ind.quantity <> quantity) or (ind.value <> value) or (ind.depot <> depot) or (ind.depotdetail <> depotdetail):
                ins = ind.inid
                if ins.log is None:
                    ins.log = ""
                ins.log = u"%s %s 修改 产品：%s\n原:%s套 单价%s 仓库%s\n新:%s套 单价%s 仓库%s\n%s\n"\
                %(datetime.date.today(),request.user.get_profile().name,ind.product.name,ind.quantity,ind.value,ind.depot.name,quantity,value,depot.name,31*'-') + ins.log
                ind.quantity = quantity
                ind.value = value
                ind.depot = depot
                ind.depotdetail = depotdetail
                ind.save()
                ins.save()
        return HttpResponse(simplejson.dumps({"flag":flag,"msg":"</br>".join(msg)},ensure_ascii=False), mimetype="text/plain")

    else:
        url = ""
        instream = ""
        if act == "detail":
            page_title="入库详单"
            instream = get_object_or_404(InStream, id=iId)
            ins = InDetail.objects.filter(inid=instream,quantity__gt=0).order_by("-id")
            url = "act=%s&id=%s&"%(act,iId)
        
        else:
            if act == "search":
                pid = get_object_or_404(Products, id=iId)
                pname = pid.name
                did=request.GET.get("did","0")
                if did == "0":
                    inds = InDetail.objects.filter(product=pid,quantity__gt=0).values_list("inid")
                else:
                    inds = InDetail.objects.filter(product=pid,quantity__gt=0,depot=did).values_list("inid")
                ins = InStream.objects.filter(id__in=inds).order_by("-id")
                slist = InDetail.objects.filter(inid__in=ins,quantity__gt=0,product=pid).values("inid","product").annotate(tq=Sum("quantity")).order_by("-inid")
                for (i,q) in zip(ins,slist):
                    i.pq = q["tq"]
                url = "act=search&id=%s&did=%s&"%(iId,did)
            else:
                ins = InStream.objects.order_by("-id")
        paginator = Paginator(ins, 20)
        after_range_num = 5      #当前页前显示5页
        befor_range_num = 4      #当前页后显示4页
        try:#如果请求的页码少于1或者类型错误，则跳转到第1页
            page = int(request.GET.get("page",1))
            if page < 1:
                page = 1
        except ValueError:
            page = 1
        ins_list = paginator.page(page)
        if page >= after_range_num:
            page_range = paginator.page_range[page-after_range_num:page+befor_range_num]
        else:
            page_range = paginator.page_range[0:int(page)+befor_range_num]

        return render_to_response('app/depots_instream.html',{"page_title":page_title,"ins_list":ins_list,"page_range":page_range,"rows":len(ins),"instream":instream,"level":level,"url":url,"pname":pname})

def ypsi_depots_out(request,direction):
    act = request.GET.get("act","list")
    oId = request.GET.get("id","")
    level = request.user.get_profile().level
    if direction == "re":
        tt = "退"
        rFlag = True
    else:
        tt = "出"
        rFlag = False
    page_title = "%s库单列表"%tt
    pname = ""
    ototal = 0
    if act == "add":
        page_title = "新增%s库提要信息"%tt
        if request.POST:
            form = yforms.OutStream(request.POST)
            if form.is_valid():
                fc = form.cleaned_data
                outstream = OutStream(code=fc["code"],shop=fc["supplier"],date=fc["date"],keeper=fc["keeper"],staff1=fc["staff1"],note=fc["note"],returned=rFlag)
                outstream.save()
                if fc["instream"]:
                    inlist =InDetail.objects.filter(inid=fc["instream"])
                    for i in inlist:
                        OutDetail(outid=outstream,product=i.product,quantity=i.quantity,depot=i.depot).save()
                return HttpResponseRedirect("?act=added")
            else:
                return render_to_response('app/depots_outstream.html',{"page_title":"新增信息错误","form":form,"act":"add","tt":tt})

        else:
            form = yforms.OutStream()
            return render_to_response('app/depots_outstream.html',{"page_title":page_title,"form":form,"act":"add","tt":tt})

    elif act == "edit":
        out = get_object_or_404(OutStream, id=oId)
        if request.POST:
            form = yforms.OutStream(request.POST)
            if form.is_valid():
                fc = form.cleaned_data
                if (out.code<>fc["code"]) or (out.shop<>fc["supplier"]) or (out.date<>fc["date"]) or (out.keeper<>fc["keeper"]) or (out.staff1<>fc["staff1"]) or (out.hidden<>fc["hidden"]) or (out.note<>fc["note"]) :
                    out.code=fc["code"]
                    out.shop=fc["supplier"]
                    out.date=fc["date"]
                    out.keeper=fc["keeper"]
                    out.staff1=fc["staff1"]
                    out.hidden=fc["hidden"]
                    out.note=fc["note"]
                    out.save()
                return HttpResponseRedirect("?act=edited")
        else:
            form = yforms.OutStream({"code":out.code,"supplier":out.shop.id,"date":out.date,"keeper":out.keeper_id,"staff1":out.staff1_id,"hidden":out.hidden,"note":out.note,"log":out.log})
            page_title = "%s库提要信息"%tt

        return render_to_response('app/depots_outstream.html',{"page_title":page_title,"form":form,"oId":oId})

    elif act == "del":
        msg = "fail"
        if request.method == "POST":
            outstream = get_object_or_404(OutStream, id=request.POST.get("id",""))
            outstream.hidden = True
            outstream.save()
            msg = "success"
        return HttpResponse(msg, mimetype="text/plain")
    
    elif act == "d_add":
        product = get_object_or_404(Products, id=request.POST.get("pid",""))
        depot = get_object_or_404(Depot, id=request.POST.get("depot",""))
        out = get_object_or_404(OutStream, id=request.POST.get("outid",""))
        quantity = request.POST.get("quantity","")
        msg = []
        flag = True
        odid = ""
        r_str2 = 0
        regQ = re.match(ur"^[1-9][0-9]*$",quantity)
        if regQ is None:
            flag = False
            msg.append("产品数量错误")
        if flag:
            if rFlag:
                quantity = -int(quantity)
            outd = OutDetail(outid=out,product=product,quantity=quantity,depot=depot)
            outd.save()
            odid = outd.id
            productId = outd.product_id
            shopId = outd.outid.shop_id
            cursor = connection.cursor()
            cursor.execute("select oQuantity-ifNull(sQuantity,0) as nQuantity from \
            (select sum(quantity) as oQuantity,product_id as pid from PSI_OutDETAIL,psi_outStream  \
             where outId_id=psi_outStream.id and psi_outstream.hidden=0 and product_id=%s and shop_id=%s group by product_id ) \
            left join \
            (select psi_sellOrderDetail.product_id as sPid,sum(psi_sellOrderDetail.quantity) as sQuantity from psi_sellOrderDetail,psi_sellOrder \
            where product_id=%s and hidden=0 and oid_id=psi_sellOrder.id and shop_id=%s group by psi_sellOrderDetail.product_id) \
            on pid=sPid order by nQuantity desc",[productId,shopId,productId,shopId])
            tags = cursor.fetchone()
            cursor.close()
            if tags:
                r_str2 = tags[0]
        return HttpResponse(simplejson.dumps({"flag":flag,"id":odid,"squantity":r_str2,"msg":msg},ensure_ascii=False), mimetype="text/plain")

    elif act =="d_edit":
        oId = request.POST.get("id","")
        outd = get_object_or_404(OutDetail, id=oId)
        pt =get_object_or_404(Products,id=request.POST.get("pid",""))
        depot = get_object_or_404(Depot,id=request.POST.get("depot",""))
        psum = depot_pSum(depot.id,outd.product_id)
        quantity = request.POST.get("quantity","")
        msg = []
        flag = True
        regQ = re.match(ur"^[1-9][0-9]*$",quantity)
        if rFlag:
            quantity = -int(quantity)
        if regQ is None:
            flag = False
            msg.append("产品数量错误")
        elif int(quantity)>(int(psum)+outd.quantity):
            flag = False
            msg.append("出库数不可大于此商品当前仓库库存数")
        elif len(OutDetail.objects.exclude(id=oId).filter(outid=outd.outid,product=pt,depot=depot,quantity__gt=0))>0:
            flag = False
            msg.append("当前出库单中已包含同一仓库同一产品出库记录")
        if flag:
            if (outd.quantity <> quantity) or (outd.depot <> depot) :
                outs = outd.outid
                if outs.log is None:
                    outs.log = ""
                outs.log = u"%s %s 修改 产品：%s\n原:%s套 仓库%s\n新:%s套 仓库%s\n%s\n"\
                %(datetime.date.today(),request.user.get_profile().name,outd.product.name,outd.quantity,outd.depot.name,quantity,depot.name,31*"-") + outs.log
                outd.quantity=quantity
                outd.depot = depot
                outd.save()
                outs.save()
        return HttpResponse(simplejson.dumps({"flag":flag,"msg":msg},ensure_ascii=False), mimetype="text/plain")

    elif act=="d_del":
        oId = request.POST.get("id","")
        outd = get_object_or_404(OutDetail, id=oId)
        #flag = True
        #尚缺出库删除后相应店铺历史销售数据逻辑错误判断
        outs = outd.outid
        if outs.log is None:
            outs.log = ""
        outs.log = u"%s %s 删除 产品：%s\n原:%s套 仓库%s\n%s\n"\
        %(datetime.date.today(),request.user.get_profile().name,outd.product.name,outd.quantity,outd.depot.name,31*'-') + outs.log
        outd.quantity = 0
        outd.save()
        outs.save()
        return HttpResponse("done", mimetype="text/plain")
    
    else:
        url = ""
        outstream = ""
        if act == "detail":
            page_title="%s库详单"%tt
            outstream = get_object_or_404(OutStream, id=oId, returned=rFlag)
            out = OutDetail.objects.filter(outid=outstream).exclude(quantity=0).order_by("-id")
            if  rFlag:
                out = out.extra(select={"squantity":0})
            url = "act=%s&id=%s&"%(act,oId)
        else:
            if act == "search":
                pid = get_object_or_404(Products, id=oId)
                pname = pid.name
                did = request.GET.get("did","0")
                sid = request.GET.get("sid","0")
                hide = request.GET.get("hidden","false")

                if did == "0":
                    outds = OutDetail.objects.filter(product=pid,outid__returned=rFlag).exclude(quantity=0)
                else:
                    outds = OutDetail.objects.filter(product=pid,outid__returned=rFlag,depot=did).exclude(quantity=0)
                if sid <> "0":
                    outds = outds.filter(outid__shop=get_object_or_404(Shop, id=sid))
                if hide == "true":
                    out = OutStream.objects.filter(id__in=outds.values_list("outid")).order_by("-id")
                else:
                    out = OutStream.objects.filter(id__in=outds.values_list("outid")).exclude(hidden=1).order_by("-id")
                slist = OutDetail.objects.filter(outid__in=out,product=oId).exclude(quantity=0).values("outid","product").annotate(tq=Sum("quantity")).order_by("-outid")

                for (o,q) in zip(out,slist):
                    o.pq = q["tq"]
                    ototal += o.pq#当前出库总数

                url = "act=search&id=%s&did=%s&sid=%s&hidden=%s&"%(oId,did,sid,hide)
            else:
                if rFlag:
                    out = OutStream.objects.filter(returned=1).order_by("-id")
                else:
                    out = OutStream.objects.filter(returned=0).order_by("-id")
        paginator = Paginator(out, 20)
        after_range_num = 5      #当前页前显示5页
        befor_range_num = 4      #当前页后显示4页
        try:#如果请求的页码少于1或者类型错误，则跳转到第1页
            page = int(request.GET.get("page",1))
            if page < 1:
                page = 1
        except ValueError:
            page = 1
        out_list = paginator.page(page)
        if act == "detail" and rFlag:
            shopId = outstream.shop_id
            cursor = connection.cursor()
            for od in out_list.object_list:
                cursor.execute("select oQuantity-ifNull(sQuantity,0) as nQuantity from \
                (select sum(quantity) as oQuantity,product_id as pid from PSI_OutDETAIL,psi_outStream  \
                 where outId_id=psi_outStream.id and psi_outstream.hidden=0 and product_id=%s and shop_id=%s group by product_id ) \
                left join \
                (select psi_sellOrderDetail.product_id as sPid,sum(psi_sellOrderDetail.quantity) as sQuantity from psi_sellOrderDetail,psi_sellOrder \
                where product_id=%s and hidden=0 and oid_id=psi_sellOrder.id and shop_id=%s group by psi_sellOrderDetail.product_id) \
                on pid=sPid order by nQuantity desc",[od.product.id,shopId,od.product.id,shopId])
                od.squantity = cursor.fetchone()[0]
                od.save()
            cursor.close()
        if page >= after_range_num:
            page_range = paginator.page_range[page-after_range_num:page+befor_range_num]
        else:
            page_range = paginator.page_range[0:int(page)+befor_range_num]
        return render_to_response('app/depots_outstream.html',{"page_title":page_title,"out_list":out_list,"page_range":page_range,"rows":len(out),"outstream":outstream,"level":level,"url":url,"pname":pname,"ototal":ototal,"tt":tt})

def ypsi_depots_remit(request):
    act = request.GET.get("act","list")
    rId = request.GET.get("id","")
    level = request.user.get_profile().level
    
    if act == "adding":
        form = yforms.RemitAdd(request.POST)
        if form.is_valid():
            fc = form.cleaned_data
            Remit(supplier=fc["supplier"],date=fc["date"],amount=fc["amount"],staff=fc["staff"],note=fc["note"]).save()
            act = "added"
        else:
            act = "add"
        return render_to_response('app/depots_remit.html',{"page_title":"记录添加成功 正在跳转","form":form,"act":act})
    elif act == "add":
        return render_to_response('app/depots_remit.html',{"page_title":"添加汇款记录","form": yforms.RemitAdd(),"act":act,"level":level})
    elif act == "edit" and rId and request.POST:
        rmt = get_object_or_404(Remit, id=rId)
        form = yforms.RemitAdd(request.POST)
        if form.is_valid():
            fc = form.cleaned_data
            rmt.supplier = fc["supplier"]
            rmt.date = fc["date"]
            rmt.amount = fc["amount"]
            rmt.staff = fc["staff"]
            rmt.hidden = fc["hidden"]
            rmt.note = fc["note"]
            rmt.save()
            return render_to_response('app/depots_remit.html',{"page_title":"记录修改成功 正在跳转","form":form,"act":"edited","level":level})
        else:
            return render_to_response("app/depots_remit.html",{"page_title":"非法数据","form":form,"act":"edit","rId":rId})
    elif act == "edit" and rId:
        rmt = get_object_or_404(Remit, id=rId)
        form = yforms.RemitAdd({"supplier":rmt.supplier,"date":rmt.date,"amount":rmt.amount,"staff":rmt.staff_id,"hidden":rmt.hidden,"note":rmt.note})
        return render_to_response('app/depots_remit.html',{"page_title":"添加汇款记录","form": form,"act":act,"rId":rId,"level":level})
    else :
        rmts = Remit.objects.order_by("-id")
        paginator = Paginator(rmts, 20)
        after_range_num = 5
        befor_range_num = 4
        try:
            page = int(request.GET.get("page",1))
            if page < 1:
                page = 1
        except ValueError:
            page = 1
        rmts_list = paginator.page(page)
        if page >= after_range_num:
            page_range = paginator.page_range[page-after_range_num:page+befor_range_num]
        else:
            page_range = paginator.page_range[0:int(page)+befor_range_num]

        return render_to_response('app/depots_remit.html',{"page_title":"汇款记录列表","r_list":rmts_list,"act":act,"page_range":page_range,"rows":len(rmts),"level":level})

@login_required()
def ypsi_staff(request):
    sid = request.GET.get("id","")
    act = request.GET.get("act","")
    if act == "pwd":
        if request.method == "POST":
            errmsg =""
            form =yforms.PWd(request.POST)
            user = get_object_or_404(User,id=request.POST.get("sid"))
            page_title = "密码修改中"
            if form.is_valid():
                pwd = request.POST.get("pwd")
                cd = form.cleaned_data
                if pwd==cd["pwd2"]:
                    if user.check_password(cd["opwd"]):
                        user.set_password(pwd)
                        user.save()
                        return HttpResponseRedirect("?act=pwd_changed")
                    else:
                        errmsg = "id_opwd,原密码错误。"
                else:
                    errmsg = "id_pwd,两次密码输入不一致。"
            return render_to_response("app/staff.html",{"page_title":page_title,"form":form,"errmsg":errmsg,"sid":request.POST.get("sid")})
            


        else:
            page_title = u"%s密码修改"%request.user.get_profile().name
            form =yforms.PWd()
            return render_to_response("app/staff.html",{"page_title":page_title,"form":form,"sid":request.user.id})


    else:
        page_title = "个人资料"
        staff_list = Staff.objects.filter(level__lt=99).order_by("-shop","level")
        if sid:
            staff =  get_object_or_404(Staff,id=sid)
        else:
            staff = request.user.get_profile

        return render_to_response("app/staff.html",{"page_title":page_title,"staff_list":staff_list,"staff":staff})

@login_required()
def ypsi_customer(request):
    #form = yforms.CustomerAdd(request.POST)
    act = request.GET.get("act","")
    cid = request.GET.get("id","0")
    level = request.user.get_profile().level
    if act =="chart":
        cursor = connection.cursor()
        cursor.execute("select date(date),sum(quantity*price)-(ifnull(discount,0)) as total from psi_sellorderdetail,psi_sellorder where psi_sellorder.hidden=0 and psi_sellorder.id=psi_sellorderdetail.oid_id and psi_sellorder.customer_id=%s group by psi_sellorder.id order by date",[cid])
        olist = cursor.fetchall()
        cursor.close()
        jstr ={"date":[],"amount":[]}
        if len(olist)>0:
            for o in olist:
                jstr["date"].append(o[0])
                jstr["amount"].append(o[1])
        return HttpResponse(simplejson.dumps(jstr), mimetype='application/json')
    
    elif act == "search":
        ctm =""
        if request.method == "POST":
            cid = request.POST.get("id","0")
            ctm = get_object_or_404(Customer,id=cid)
        return render_to_response("app/customer.html",{"page_title":"会员详细资料","ctm":ctm,"act":act})
    elif int(cid)>0:
        ctm = get_object_or_404(Customer,id=cid)
        return render_to_response("app/customer.html",{"page_title":"会员详细资料","ctm":ctm})
    else:
        if act == "showall" :
            page_title = "所有会员列表"
            ctms = Customer.objects.order_by("-id")
        else:
            page_title = "会员列表"
            ctms = Customer.objects.filter(shop=request.user.get_profile().shop).order_by("-id")
        paginator = Paginator(ctms, 20)
        after_range_num = 5
        befor_range_num = 4
        try:
            page = int(request.GET.get("page",1))
            if page < 1:
                page = 1
        except ValueError:
            page = 1
        ctms_list = paginator.page(page)
        if page >= after_range_num:
            page_range = paginator.page_range[page-after_range_num:page+befor_range_num]
        else:
            page_range = paginator.page_range[0:int(page)+befor_range_num]

        return render_to_response("app/customer.html",{"page_title":page_title,"r_list":ctms_list,"page_range":page_range,"rows":len(ctms),"act":act,"shop_id":request.user.get_profile().shop_id,"level":level})
    #return render_to_response("app/customer.html")

def ypsi_category(request):
    act = request.GET.get("act","")
    if act == "list":
        jsonclist = []
        if 'id' in request.GET:
            pid = request.GET["id"]
            cjlist = Category.objects.filter(hidden=0,pid=pid)
        else :
            cjlist = Category.objects.filter(hidden=0)


        for cj in cjlist:
            #c = {}
            #c['id'] = cj.id
            if cj.pid_id:
                jsonclist.append({"id":cj.id,"pId":cj.pid_id,"name":cj.name})
                #c['pId'] = cj.pid_id
            else:
                jsonclist.append({"id":cj.id,"pId":0,"name":cj.name})
                #c['pId'] = 0
            #c['name'] = cj.name

            #jsonclist.append(c)
        return HttpResponse(simplejson.dumps(jsonclist), mimetype='application/json')

    elif act=="edit":
        if request.method == 'POST':
            #print request.raw_post_data
            clist = eval(request.raw_post_data)

            cid_list = []
            cid_old_list=[]
            for c in clist:
                 cid_list.append(c['id'])

            c_old = Category.objects.all()
            for cd in c_old:
                cid_old_list.append(cd.id)

            cid_old_list.sort()
            cid_list.sort()

            cid_old_list_set = set(cid_old_list)
            cid_list_set = set(cid_list)

            #更新分类数据
            cid_list_x = cid_old_list_set & cid_list_set #提取更新部分ID
            c1 = Category.objects.filter(id__in=cid_list_x)#初步筛选
            for c in clist:
                try:
                    c1c = c1.get(id=c['id'])
                    if not (c1c.name == unicode(c['name'],'UTF-8') and c1c.pid_id == c['pId']):#加入判断，减少数据库写操作
                        #print c['name']
                        c1c.name=unicode(c['name'],'UTF-8')
                        if c["pId"] == None:
                            c1c.pid = None
                        else:
                            c1c.pid=get_object_or_404(Category,id=c['pId'])
                        c1c.save()
                except Exception as error:#因新分类库可能大于原有分类库，故会出现"not exist"错误，在此抛出
                    #print error
                    continue

            #删除分类,未完全完成下属分类产品标记删除
            cid_list_x = cid_old_list_set - cid_list_set #提取被删除部分ID
            c_del = Category.objects.filter(id__in=cid_list_x)
            c_del.update(hidden=True)
            Products.objects.filter(category__in=c_del).update(hidden=True)


            #新增分类
            cid_list_x = cid_list_set - cid_old_list_set #提取新增部分ID
            for c in clist:
                try:
                    cid_list_x.remove(c['id'])#set无直接索引办法，故使用删除，然后异常抛出处理
                    c_add = Category(name=unicode(c['name'],'UTF-8'),pid=get_object_or_404(Category,id=c['pId']))
                    c_add.save()
                    for i in range(len(clist)):#更新原始数据中的pId值，避免数据库开销
                        if clist[i]['pId'] == c['id']:
                            clist[i]['pId'] = c_add.id
                except Exception as error:
                    continue
        return HttpResponse(simplejson.dumps({"flag":True}), mimetype='application/json')
    else:
        page_title = "类别管理"
        level = request.user.get_profile().level
        return render_to_response("app/category.html",{"page_title":page_title,"level":level})

#from django.forms.util import ErrorList
def ypsi_customer_mini(request):
    cid = request.GET.get("id","0")
    if request.method == "POST":
        form = yforms.CustomerAdd(request.POST)
        '''
        el = ErrorList()
        el.append(u"中文哦")
        form.errors["name"] = el
        print form._errors
        print "--------"
        print form.errors
        print "--------"
        '''
        #s_str = eval(request.raw_post_data)
        #print form
        #print form.errors.keys()
        #print "--------"
        #form.errors['name']="c"
        #print form.errors['name']
        #print form.is_valid()
        #print "--------"
        if form.is_valid():
            shopId = get_object_or_404(Shop, id=request.user.get_profile().shop_id)
            c = form.cleaned_data
            if cid=="0":
                c1 = Customer(name=c["name"],code=c["code"],telephone=c["telephone"],shop=shopId,joindate=c["joindate"],address=c["address"],note=c["note"])
            else:
                c1 = get_object_or_404(Customer, id=cid)
                c1.name = c["name"]
                c1.code = c["code"]
                c1.telephone= c["telephone"]
                c1.shop = shopId
                c1.joindate = c["joindate"]
                c1.address = c["address"]
                c1.note = c["note"]
            c1.save()
            tt = {"flag":True,"id":c1.id,"name":form.cleaned_data['name']}
        else:
            tt ={"flag":False,"data":[]}

            for f in form.errors:
                tt["data"].append({"key":f,"value":form.errors[f]})
        return HttpResponse(simplejson.dumps(tt,ensure_ascii=False), mimetype="text/plain")

    else:
        if cid=="0":
            page_title = "添加本店客户"
            form = yforms.CustomerAdd()
        else:
            page_title = "客户资料修改"
            ctm = get_object_or_404(Customer, id=cid)
            form = yforms.CustomerAdd({"name":ctm.name,"code":ctm.code,"telephone":ctm.telephone,"joindate":ctm.joindate,"address":ctm.address,"note":ctm.note})
        return render_to_response('app/customer_mini.html',{"page_title":page_title,"form":form,"cid":cid})

def ypsi_product_mini(request):
    p_id =  request.GET.get("id","")
    act = request.GET.get("act","")
    if p_id:
        if request.method == "POST":
            form = yforms.Product(request.POST)
            if form.is_valid():
                c = form.cleaned_data
                pd = get_object_or_404(Products, id=p_id)
                cgId = get_object_or_404(Category, id=request.POST.get("category"))
                pd.name = c["name"]
                pd.barcode = c["barcode"]
                pd.category = cgId
                pd.size = c["size"]
                pd.hidden = c["hidden"]
                pd.note = c["note"]
                pd.save()
                return HttpResponse(simplejson.dumps({"flag":True},ensure_ascii=False), mimetype="text/plain")
            else:
                return HttpResponse(simplejson.dumps({"flag":False},ensure_ascii=False), mimetype="text/plain")

        else:
            page_title = "产品信息修改"
            pd = get_object_or_404(Products,id=p_id)
            form=yforms.Product({"name":pd.name,"barcode":pd.barcode,"size":str(pd.size).replace("\"",""),"category":pd.category_id,"hidden":pd.hidden,"note":pd.note})
            plist = Category.objects.filter(hidden=0,pid__isnull=False).distinct("pid").values_list("pid")
            d0 = Category.objects.filter(hidden=0).exclude(id__in=plist).order_by("pid")
            return render_to_response('app/product_mini.html',{"page_title":page_title,"form":form,"cg_id":pd.category_id,"cc":d0,"level":request.user.get_profile().level})

    elif act== "add" :
        if request.method == "POST":
            form = yforms.Product(request.POST)
            if form.is_valid():
                cgId = get_object_or_404(Category, id=request.POST.get("category"))
                c = form.cleaned_data
                p1 = Products(name=c["name"],barcode=c["barcode"],size=c["size"],category=cgId,note=c["note"])
                p1.save()
                tt = {"flag":True,"id":p1.id,"name":form.cleaned_data['name']}
            else:
                tt ={"flag":False,"data":[]}

                for f in form.errors:
                    tt["data"].append({"key":f,"value":form.errors[f]})
            return HttpResponse(simplejson.dumps(tt,ensure_ascii=False), mimetype="text/plain")
        else:
            return HttpResponse("error")
    else:
        page_title = "添加产品"
        #c0 = Category.objects.filter(hidden=0,pid__in = Category.objects.filter(hidden=0,pid=None))
        plist = Category.objects.filter(hidden=0,pid__isnull=False).distinct("pid").values_list("pid")
        d0 = Category.objects.filter(hidden=0).exclude(id__in=plist).order_by("pid")
        form = yforms.Product()
        return render_to_response('app/product_mini.html',{"page_title":page_title,"form":form,"cc":d0,"level":request.user.get_profile().level})

def ypsi_product_checkdata(request):
    model = request.GET.get("model","")
    data = request.GET.get("data","")
    result = ""
    if model == "name":
        result = Products.objects.filter(hidden=0,name=data)
    elif model == "barcode":
        result = Products.objects.filter(hidden=0,barcode=data)
    count = len(result)

    return HttpResponse(count,mimetype="text/plain")

def ypsi_customer_checkdata(request):
    model = request.GET.get('model',"")
    data = request.GET.get('data',"")
    tags = ""
    #json_str = {"flag":True,"data":[]}
    if model == "name":
        tags = Customer.objects.filter(hidden=0,name=data)
    elif model == "code":
        tags = Customer.objects.filter(hidden=0,code=data)
    elif model == "telephone":
        tags = Customer.objects.filter(hidden=0,telephone=data)
    if len(tags) > 0:
        '''json_str["flag"]=False
        for tag in tags:
            json_str["data"].append({"name":tag.name,"code":tag.code,"telephone":tag.telephone})'''
    return HttpResponse(len(tags),mimetype="text/plain")




