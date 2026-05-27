import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AlignXLogo } from "@/components/AlignXLogo";

const sections = [
  {
    title: "1. 协议适用",
    body: "本协议适用于你访问和使用 AlignX 网站、内测工作台、AI 诊断、ASIN 选品、Listing 分析、广告验证、数据回流、报告导出及后续上线的相关服务。你点击同意、登录或继续使用，即表示你已阅读、理解并接受本协议。",
  },
  {
    title: "2. 账号注册与安全",
    body: "内测阶段以邮箱验证码作为主要登录方式。你应使用真实、有效、可接收验证码的邮箱，并妥善保管邮箱账号和登录凭证。因你主动泄露验证码、邮箱被盗用或授权他人使用造成的操作和数据风险，由你自行承担。",
  },
  {
    title: "3. 服务内容",
    body: "AlignX 提供面向亚马逊运营场景的决策辅助能力，包括但不限于 ASIN 机会判断、Listing 上新检测、本品诊断、竞品诊断、广告假设验证、效果复盘和下一轮优化建议。具体功能、额度、价格和可用范围以页面展示或双方约定为准。",
  },
  {
    title: "4. 用户内容与授权",
    body: "你确认对上传或提交的 ASIN、商品标题、五点描述、图片信息、A+内容、关键词、广告数据、评论数据、店铺信息及其它资料拥有合法使用权。为提供服务，你授权 AlignX 在必要范围内存储、处理、分析、生成报告和用于改进诊断规则。",
  },
  {
    title: "5. 禁止行为",
    body: "你不得利用本服务从事违法违规、侵犯知识产权、侵犯隐私、破坏系统安全、批量恶意请求、绕过权限控制、爬取或倒卖系统数据、上传恶意代码、冒用他人身份或违反亚马逊及其它平台规则的行为。",
  },
  {
    title: "6. AI 输出与经营风险",
    body: "AlignX 的 AI 输出基于用户输入、公开页面、抓取结果、规则模型和算法推理生成，仅作为经营决策参考，不构成销量承诺、利润承诺、广告效果保证、法律意见或亚马逊平台合规结论。你应结合自身经验、真实广告数据、供应链能力和平台政策独立判断后执行。",
  },
  {
    title: "7. 数据隔离与管理员访问",
    body: "系统按登录邮箱隔离普通用户数据，同邮箱历史身份会合并读取。超级管理员可在后台查看用户测试内容，但仅限于内测支持、故障排查、合规审计、数据安全处理、用户授权服务和产品改进所需范围。",
  },
  {
    title: "8. 费用与额度",
    body: "免费试用、付费套餐、加量包、团队版和企业版的权益、额度、有效期、价格和支付方式以产品页面或双方确认的信息为准。内测期间部分功能可能免费开放或调整，正式商业化前会另行提示。",
  },
  {
    title: "9. 服务变更、中断与终止",
    body: "因产品迭代、系统维护、第三方服务异常、云服务故障、网络攻击、政策调整或不可抗力等原因，服务可能发生变更、中断或终止。我们会尽合理努力降低影响，但不保证服务永久、连续、无错误或完全符合你的预期。",
  },
  {
    title: "10. 知识产权",
    body: "AlignX 的产品界面、流程设计、算法规则、诊断模型、文档、商标、代码和系统结构等知识产权归 AlignX 或相关权利人所有。未经授权，你不得复制、反向工程、转售、转授权或用于开发竞争性产品。",
  },
  {
    title: "11. 责任限制",
    body: "在法律允许范围内，AlignX 不对因使用或无法使用服务导致的间接损失、利润损失、商誉损失、数据损失、广告费用损失、账号处罚、供应链损失或第三方索赔承担责任。对于可归责于 AlignX 的直接损失，赔偿上限不超过你在争议发生前 3 个月实际支付给 AlignX 的服务费用。",
  },
  {
    title: "12. 适用法律与争议解决",
    body: "本协议的订立、履行和解释适用中华人民共和国法律。因本协议或服务产生争议，双方应先友好协商；协商不成的，提交 AlignX 运营主体所在地有管辖权的人民法院处理。",
  },
  {
    title: "13. 协议更新",
    body: "我们可能根据法律法规、产品迭代、商业安排或数据处理方式变化更新本协议。重大变化会通过页面提示、公告或其它合理方式通知。更新后继续使用服务，即表示你接受更新后的协议。",
  },
];

export default function Terms() {
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
            <h1 className="text-3xl font-bold">AlignX 用户协议</h1>
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
            <Button onClick={() => navigate("/privacy")} variant="outline">
              查看隐私政策
            </Button>
          </div>
        </Card>
      </main>
    </div>
  );
}
