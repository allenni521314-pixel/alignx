import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AlignXLogo } from "@/components/AlignXLogo";

const sections = [
  {
    title: "1. 政策适用",
    body: "本政策适用于你访问和使用 AlignX 网站、内测工作台、Listing 诊断、ASIN 选品、Listing 分析、广告验证、数据回流、报告导出和相关服务时的信息处理活动。",
  },
  {
    title: "2. 我们收集的信息",
    body: "我们可能收集你的登录邮箱、公司或店铺名称、账号角色、登录时间、ASIN、商品标题、五点描述、主图和附图描述、A+内容、后台关键词、竞品信息、评论信息、广告验证数据、诊断结果、历史快照、导出和删除申请、设备与日志信息。",
  },
  {
    title: "3. 信息使用目的",
    body: "我们使用上述信息用于账号登录与验证、邮箱租户隔离、生成诊断报告、保存历史记录、构建广告验证闭环、提供客户支持、排查系统故障、保障账号和数据安全、改进产品诊断效果、履行法律法规要求。",
  },
  {
    title: "4. 数据隔离与访问控制",
    body: "普通用户只能访问自己邮箱租户下的数据。同邮箱历史身份会合并读取，以保证重新登录后的历史连续性。超级管理员仅可在后台基于运营支持、审计、故障排查、数据安全和用户授权目的访问用户数据。",
  },
  {
    title: "5. 第三方处理",
    body: "为提供服务，我们可能使用云服务器、数据库、智能诊断服务、邮件验证码、页面抓取、日志监控和部署平台等第三方基础设施。我们会尽量只传递完成服务所必需的信息，并要求相关处理活动围绕服务目的进行。",
  },
  {
    title: "6. Cookie 与本地存储",
    body: "我们可能使用浏览器本地存储保存登录令牌、用户信息、记住登录状态和页面偏好，用于维持登录状态和改善使用体验。你可以通过退出登录或清理浏览器数据删除本地信息，但可能影响正常使用。",
  },
  {
    title: "7. 数据保存",
    body: "我们会在实现服务目的所需期间保存你的数据。内测期间，为保证诊断历史、广告验证和复盘闭环的连续性，部分数据会持续保存，除非你提交删除申请并经复核处理，或法律法规另有要求。",
  },
  {
    title: "8. 导出、更正与删除",
    body: "你可以在设置页导出自己的数据，也可以提交删除申请。内测阶段删除申请进入人工复核流程，以避免误删影响历史诊断、广告验证和闭环复盘。我们会在合理时间内处理你的请求。",
  },
  {
    title: "9. 数据安全措施",
    body: "我们通过邮箱验证码登录、接口鉴权、邮箱租户隔离、管理员权限控制、旧认证入口关闭、健康检查和操作记录等方式保护数据安全。但互联网服务无法保证绝对安全，如发现异常访问或数据错误，请及时联系我们。",
  },
  {
    title: "10. 未成年人",
    body: "AlignX 面向亚马逊经营者和企业用户，不面向未成年人提供服务。若你是未成年人，请不要注册或提交个人信息。",
  },
  {
    title: "11. 跨境与平台数据",
    body: "你提交的亚马逊相关数据可能涉及境外平台页面、广告和商品信息。你应确保有权处理和提交相关数据，并遵守适用的平台政策、数据合规要求和法律法规。",
  },
  {
    title: "12. 政策更新",
    body: "我们可能根据产品功能、法律要求、第三方服务或数据处理方式变化更新本政策。重大变化会通过页面提示、公告或其它合理方式通知。更新后继续使用服务，即表示你接受更新后的政策。",
  },
];

export default function Privacy() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <main className="max-w-4xl mx-auto px-5 py-8">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-gray-500 hover:text-gray-900 transition-colors mb-6 text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          返回
        </button>

        <Card className="bg-white border-gray-200 p-6 sm:p-8">
          <AlignXLogo showWordmark markClassName="h-10 w-10" wordmarkClassName="text-xl" />
          <div className="mt-8 mb-6">
            <h1 className="text-3xl font-bold">AlignX 隐私政策</h1>
            <p className="text-sm text-gray-500 mt-2">生效日期：2026-05-27 · 运营主体：深圳灵曦智感科技有限公司</p>
          </div>

          <div className="space-y-6">
            {sections.map((section) => (
              <section key={section.title}>
                <h2 className="text-lg font-semibold">{section.title}</h2>
                <p className="text-sm text-gray-600 leading-7 mt-2">{section.body}</p>
              </section>
            ))}
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <Button onClick={() => navigate("/login")} className="bg-brand-600 hover:bg-brand-500 text-white">
              返回登录
            </Button>
            <Button onClick={() => navigate("/terms")} variant="outline">
              查看用户协议
            </Button>
          </div>
        </Card>
      </main>
    </div>
  );
}
