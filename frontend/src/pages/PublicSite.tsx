import { Navigate, useLocation } from "react-router-dom";

type Lang = "en" | "zh";
type PageKey = "home" | "about" | "privacy-policy" | "terms" | "data-use-policy" | "security" | "contact";
type Section = [string, string[]];
type PublicPage = { title: string; sections: Section[] };

const effectiveDate = "2026-06-29";

const company = {
  en: "Shenzhen Lingxi Zhigan Technology Co., Ltd.",
  zh: "深圳灵曦智感科技有限公司",
};

const labels = {
  en: {
    nav: ["Why AlignX", "How It Works", "Data Security", "About", "Contact"],
    paths: ["#why", "#how", "#security", "/en/about", "/en/contact"],
    login: "Log In / Start Validation",
    footerValue: "Take Control Of Every Operational Investment",
    method: "Validate Before You Invest",
    footerLinks: [
      ["Privacy Policy", "/en/privacy-policy"],
      ["Terms of Service", "/en/terms"],
      ["Data Use Policy", "/en/data-use-policy"],
      ["Security", "/en/security"],
      ["Contact", "/en/contact"],
    ],
    disclaimer:
      "AlignX is an independent software service for Amazon sellers and is not affiliated with, endorsed by, or officially sponsored by Amazon unless explicitly stated.",
  },
  zh: {
    nav: ["为什么 AlignX", "如何验证", "数据安全", "关于我们", "联系我们"],
    paths: ["#why", "#how", "#security", "/zh/about", "/zh/contact"],
    login: "登录 / 开始验证",
    footerValue: "掌握每一次运营投入",
    method: "先验证，再投入",
    footerLinks: [
      ["隐私政策", "/zh/privacy-policy"],
      ["用户协议", "/zh/terms"],
      ["数据使用政策", "/zh/data-use-policy"],
      ["安全说明", "/zh/security"],
      ["联系我们", "/zh/contact"],
    ],
    disclaimer:
      "AlignX 是面向 Amazon 卖家的独立软件服务。除非另有明确说明，AlignX 与 Amazon 不存在官方关联、官方背书或官方赞助关系。",
  },
};

const home = {
  en: {
    heroTitle: "Take Control Of Every Operational Investment",
    heroSubtitle:
      "AlignX helps Amazon sellers review products, listings, advertising and inventory decisions before scaling investment.",
    supportLine: "Validate before you invest.",
    cardTitle: "ASIN Validation Record",
    card: [
      ["Opportunity", "Pending Review"],
      ["Listing", "Needs Validation"],
      ["Ads", "Budget Check Required"],
      ["Next Action", "Verify Before Scaling"],
    ],
    painTitle: "Operations should not depend on guesswork.",
    painBody: [
      "Ads spend money, but orders do not grow.",
      "Listings get changed, but conversion drops.",
      "New products launch, but inventory gets stuck.",
      "Teams keep taking actions, but many decisions are not reviewed.",
    ],
    painClose:
      "Profit is often lost not by one ad campaign, but by a chain of unvalidated decisions.",
    helpTitle: "See clearly before you scale.",
    helpCards: [
      ["Product Opportunity Review", "Review whether a product is worth continued investment."],
      [
        "Listing Readiness Review",
        "Check whether titles, images, bullets and A+ content communicate the buyer’s key reason to purchase.",
      ],
      ["Advertising Budget Review", "Review whether ad spend should be scaled, reduced or paused."],
      [
        "Execution Records",
        "Track key actions such as listing changes, price changes, keyword changes and budget changes.",
      ],
      ["Result Review", "Use performance data to decide whether to continue, adjust or stop."],
    ],
    dataTitle: "Seller-authorized data, used only for operation validation.",
    dataBody:
      "When connected by seller authorization, AlignX may use seller data needed to support operation validation, ASIN records, listing review, advertising analysis and result tracking.",
    dataUseTitle: "Data We May Use",
    dataUse: [
      "Product and catalog data",
      "Listing content and attributes",
      "Inventory and availability data",
      "Advertising and campaign performance data",
      "Sales and business report data",
      "Account performance data, where authorized",
    ],
    dataNoTitle: "Data We Do Not Need By Default",
    dataNo: [
      "Buyer personal information",
      "Buyer messages",
      "Payment credentials",
      "Seller Central password",
      "Unrelated personal files",
    ],
    securityTitle: "Built around authorization, purpose limitation and data protection.",
    securityCards: [
      ["Authorization-Based Access", "AlignX accesses seller data only after seller authorization."],
      [
        "Purpose-Limited Use",
        "Data is used for operation validation, ASIN records, listing review, advertising analysis and result tracking.",
      ],
      ["No Seller Central Password Collection", "AlignX does not ask sellers to share their Seller Central password."],
      ["Access Control And Revocation", "Sellers can disconnect or revoke access according to authorization settings."],
    ],
    aboutTitle: "About AlignX",
    aboutBody: [
      "AlignX is an independent software service developed by Shenzhen Lingxi Zhigan Technology Co., Ltd. for Amazon sellers.",
      "We help sellers validate operational decisions before scaling investments in products, listings, advertising and inventory.",
      "AlignX focuses on operation validation, decision review and performance analysis. We do not operate Seller Central accounts on behalf of sellers, do not collect Seller Central passwords, and do not claim to be affiliated with, endorsed by, or officially sponsored by Amazon.",
    ],
    aboutFacts: [
      ["Company", company.en],
      ["Product", "AlignX"],
      ["Service Type", "Amazon seller operation validation software"],
      ["Contact", "support@alignxagent.com"],
    ],
    usersTitle: "Built for sellers who want fewer wrong investments.",
    users: [
      "Multi-SKU Amazon sellers",
      "New product testing teams",
      "Sellers with significant advertising spend",
      "Operations managers",
      "Brand sellers who want clearer ASIN-level decisions",
    ],
  },
  zh: {
    heroTitle: "掌握每一次运营投入",
    heroSubtitle:
      "AlignX 帮助 Amazon 卖家在产品、Listing、广告和库存投入放大之前，先看清问题、判断方向，再决定是否投入。",
    supportLine: "先验证，再投入。",
    cardTitle: "ASIN 验证记录",
    card: [
      ["产品机会", "待判断"],
      ["Listing", "需要验证"],
      ["广告", "需要预算复盘"],
      ["下一步", "先验证，再放大"],
    ],
    painTitle: "运营不该靠猜。",
    painBody: [
      "广告烧了，订单没涨。",
      "Listing 改了，转化掉了。",
      "新品上了，库存压住了。",
      "团队每天都在操作，但很多动作没有依据。",
    ],
    painClose: "真正亏掉利润的，往往不是一笔广告费。而是一连串没有验证过的决定。",
    helpTitle: "在投入之前，先看清楚。",
    helpCards: [
      ["产品机会判断", "判断这个产品是否值得继续投入。"],
      ["Listing 承接检查", "判断标题、图片、五点和 A+ 是否说清楚买家真正关心的购买理由。"],
      ["广告预算复盘", "判断广告预算该放大、收缩，还是暂停。"],
      ["执行记录", "记录改图、调价、换词、调预算等关键动作。"],
      ["效果复盘", "用真实数据判断继续、调整，还是停止。"],
    ],
    dataTitle: "仅在卖家授权后，使用经营验证所需的数据。",
    dataBody:
      "在卖家授权接入后，AlignX 可能使用经营验证所需的卖家数据，用于 ASIN 经营档案、Listing 检查、广告分析和效果复盘。",
    dataUseTitle: "可能使用的数据",
    dataUse: [
      "商品和目录数据",
      "Listing 内容和属性",
      "库存和可售状态数据",
      "广告和广告活动表现数据",
      "销售和业务报表数据",
      "在授权范围内的账号表现数据",
    ],
    dataNoTitle: "默认不需要的数据",
    dataNo: [
      "买家个人信息",
      "买家消息",
      "支付凭证",
      "Seller Central 登录密码",
      "与经营验证无关的个人文件",
    ],
    securityTitle: "基于授权、限定用途和数据保护。",
    securityCards: [
      ["授权后访问", "AlignX 仅在卖家授权后访问卖家数据。"],
      ["限定用途", "数据仅用于经营验证、ASIN 记录、Listing 检查、广告分析和效果复盘。"],
      ["不收集 Seller Central 密码", "AlignX 不要求卖家提供 Seller Central 登录密码。"],
      ["可撤销授权", "卖家可以根据授权设置断开或撤销访问。"],
    ],
    aboutTitle: "关于 AlignX",
    aboutBody: [
      "AlignX 是由深圳灵曦智感科技有限公司开发的独立软件服务，面向 Amazon 卖家提供经营投入验证能力。",
      "我们帮助卖家在产品、Listing、广告和库存投入放大之前，先判断问题、验证方向、记录结果。",
      "AlignX 聚焦于经营验证、决策复盘和表现分析。我们不代替卖家操作 Seller Central 账号，不收集 Seller Central 登录密码，也不声称与 Amazon 存在官方关联、官方背书或官方赞助关系。",
    ],
    aboutFacts: [
      ["公司名称", company.zh],
      ["产品名称", "AlignX"],
      ["服务类型", "Amazon 卖家经营投入验证软件"],
      ["联系方式", "support@alignxagent.com"],
    ],
    usersTitle: "适合想减少错误投入的卖家。",
    users: [
      "多 SKU Amazon 卖家",
      "新品测试团队",
      "广告投入较大的卖家",
      "运营团队负责人",
      "希望建立 ASIN 长期判断记录的品牌卖家",
    ],
  },
};

const pages: Record<Lang, Record<Exclude<PageKey, "home">, PublicPage>> = {
  en: {
    about: {
      title: "About AlignX",
      sections: [
        ["Company", [company.en]],
        ["Product", ["AlignX"]],
        ["Who We Serve", ["Amazon sellers who need operation validation before scaling investment."]],
        [
          "Service Scope",
          [
            "Product opportunity review, listing review, advertising analysis, ASIN records, execution records and result review.",
          ],
        ],
        [
          "Data Use Principles",
          [
            "Seller data is used only after authorization and only for operation validation, ASIN records, listing review, advertising analysis and result tracking.",
          ],
        ],
        ["Contact", ["support@alignxagent.com"]],
        ["Disclaimer", [labels.en.disclaimer]],
      ],
    },
    "privacy-policy": {
      title: "Privacy Policy",
      sections: [
        ["Company Information", ["Company Name: Shenzhen Lingxi Zhigan Technology Co., Ltd.", "Product Name: AlignX", "Website: alignxagent.com", "Contact Email: support@alignxagent.com", "Registered Address: Not set"]],
        ["Service Description", ["AlignX is an independent software service designed for Amazon sellers. The Service provides operation validation, ASIN operation records, listing readiness review, advertising budget review, execution tracking, result analysis, and related decision-support functions.", "AlignX is not affiliated with, endorsed by, or officially sponsored by Amazon unless expressly stated in writing."]],
        ["Definitions", ["User means any individual or entity that accesses or uses the Service.", "Seller Data means data provided by or relating to a seller's business operations, including product, catalog, listing, inventory, advertising, sales, performance, and account-related data.", "Amazon Information means any data obtained from Amazon systems, Amazon Selling Partner API, Amazon Ads API, or any Amazon-related authorization mechanism, including data made available after seller authorization.", "Personal Information means information that identifies, relates to, describes, or can reasonably be linked to an identified or identifiable individual.", "Authorized Data means data that a User has authorized AlignX to access, process, store, or analyze for purposes of providing the Service."]],
        ["Information We Collect", ["Account and contact information, including account registration information, company name, user name, email address, phone number, billing contact, business contact, support contact, AlignX login credentials, and other information submitted by the User.", "Seller-authorized Amazon Information, including product and catalog data, listing content, listing attributes, listing status, inventory, availability, fulfillment, stock-related data, advertising campaign data, keyword data, targeting, budget, bid, impression, click, spend, sales, performance data, sales data, order summary, business reports, and account performance data where authorized.", "Usage and technical information, including IP address, browser type, device information, operating system, log data, session information, access time, referring pages, feature usage, error logs, security logs, and similar technical information.", "Support and communication information submitted through support requests, contact forms, emails, customer service communications, feedback, onboarding forms, and related communications.", "Payment and billing information necessary to process payments, issue invoices, manage subscriptions, and maintain financial records if paid services are offered. Payment card or bank information may be processed by third-party payment providers. AlignX does not collect Seller Central payment credentials."]],
        ["Information We Do Not Collect By Default", ["AlignX does not ask Users to provide their Amazon Seller Central password.", "AlignX does not require buyer personal information by default.", "AlignX does not collect buyer messages by default.", "AlignX does not collect payment credentials from Amazon Seller Central.", "AlignX does not collect unrelated personal files, private documents, or personal communications unrelated to the Service.", "If any restricted, sensitive, or buyer-related information is required in the future, such collection will occur only where permitted, authorized, necessary for the specific service, and subject to additional access controls, policy requirements, and applicable legal obligations."]],
        ["How We Use Information", ["To provide, operate, maintain, and improve the Service.", "To create and maintain ASIN operation records.", "To conduct product opportunity review, listing readiness review, advertising budget review, advertising performance analysis, result review, performance analysis, and decision-support reporting.", "To record execution actions, including listing changes, pricing changes, keyword changes, campaign changes, and budget changes.", "To provide customer support and respond to inquiries.", "To manage accounts, authentication, billing, and service access.", "To monitor security, detect abuse, prevent fraud, and protect the integrity of the Service.", "To comply with applicable laws, regulations, contractual obligations, and platform policies.", "To enforce our Terms of Service and other applicable policies.", "To maintain audit logs, security records, and compliance documentation.", "To improve service quality, usability, reliability, and performance."]],
        ["Amazon Information And Seller Authorization", ["AlignX accesses Amazon Information only after seller authorization or another legally and contractually permitted authorization mechanism.", "AlignX uses Amazon Information only for the purposes authorized by the User and necessary to provide the requested Service features.", "AlignX applies purpose limitation and minimum necessary data principles when processing Amazon Information.", "AlignX does not use Amazon Information for unrelated advertising, resale, unauthorized disclosure, or unrelated product development.", "AlignX does not sell Amazon Information.", "AlignX does not use Amazon Information to manipulate rankings, manipulate reviews, circumvent Amazon systems, violate Amazon policies, or engage in unauthorized scraping or unauthorized automation."]],
        ["Legal Basis For Processing", ["Where applicable, we process Personal Information based on performance of a contract with the User, the User's consent or authorization, legitimate business interests, compliance with legal obligations, and protection of rights, property, safety, and security."]],
        ["Data Sharing And Disclosure", ["We do not sell Seller Data, Amazon Information, or Personal Information.", "We may disclose information with the User's authorization or instruction, to service providers supporting operational functions, where required by law or legal process, to protect rights or security, in connection with corporate transactions subject to appropriate protections, or to enforce our Terms of Service, policies, contracts, and legal rights.", "Any third-party service provider that processes information on our behalf must be subject to appropriate contractual, confidentiality, and data protection obligations."]],
        ["Data Storage And Security", ["We implement reasonable administrative, technical, and organizational measures designed to protect information from unauthorized access, loss, misuse, alteration, disclosure, or destruction.", "Such measures may include HTTPS and encrypted transmission, access control and user authentication, least-privilege access principles, credential protection, logging and monitoring, security review and incident response procedures, data backup and recovery controls where applicable, and separation of duties and access review where applicable.", "No method of transmission or storage is completely secure. We cannot guarantee absolute security, but we maintain measures designed to protect information in accordance with applicable legal, contractual, and policy obligations."]],
        ["Data Retention", ["We retain information only for as long as reasonably necessary to provide the Service, fulfill the purposes described in this Privacy Policy, comply with legal or contractual obligations, resolve disputes, maintain audit records, enforce agreements, prevent fraud, and protect security.", "Retention periods may vary depending on the type of data, the User's account status, legal requirements, security requirements, and service needs.", "Upon termination of the Service or written deletion request, we will delete or anonymize information within a reasonable period, unless retention is required by law, legitimate business needs, security obligations, audit obligations, dispute resolution, or contractual requirements."]],
        ["Data Deletion Requests", ["Users may request deletion of their account information, Seller Data, or Amazon Information by contacting support@alignxagent.com.", "We may verify the requester's identity and authority before processing a deletion request.", "We may retain limited information where necessary to comply with law, enforce agreements, prevent fraud, maintain security, resolve disputes, or comply with audit obligations."]],
        ["Authorization Revocation", ["Users may revoke or disconnect authorization to Amazon-related data sources according to the relevant authorization settings or by contacting support@alignxagent.com.", "After revocation, AlignX will stop new access to the relevant authorized data source, subject to technical processing time and any lawful or contractual retention obligations.", "Revocation may limit or disable certain Service features."]],
        ["International Data Transfers", ["Depending on the User's location, service configuration, hosting provider, and infrastructure, information may be processed or stored in jurisdictions other than the User's country or region.", "Where required by applicable law, we will implement appropriate safeguards for international transfers of Personal Information."]],
        ["Cookies And Similar Technologies", ["We may use cookies, local storage, analytics tools, and similar technologies to operate the Service, maintain sessions, improve performance, analyze usage, remember preferences, enhance security, and provide support.", "Users may control cookies through browser settings. Disabling cookies may affect certain Service functions."]],
        ["User Rights", ["Depending on applicable law, Users may have rights to access information, correct inaccurate information, request deletion, object to or restrict certain processing, request data portability where applicable, withdraw consent where processing is based on consent, revoke authorization to connected data sources, and submit complaints to applicable authorities where legally available.", "Requests may be submitted to support@alignxagent.com."]],
        ["Children's Privacy", ["The Service is intended for business users and is not directed to children. We do not knowingly collect Personal Information from children."]],
        ["Third-Party Services", ["The Service may contain links to third-party websites, platforms, applications, or services. We are not responsible for the privacy practices, security practices, or content of third-party services.", "Users should review the privacy policies and terms of third-party services before using them."]],
        ["Amazon Disclaimer", ["AlignX is an independent software service for Amazon sellers. Unless expressly stated in writing, AlignX is not affiliated with, endorsed by, certified by, authorized by, or officially sponsored by Amazon.", "All Amazon trademarks, service marks, and trade names remain the property of their respective owners."]],
        ["Changes To This Privacy Policy", ["We may update this Privacy Policy from time to time. The updated version will be posted on this page with an updated effective date.", "Material changes may be notified through the Service, email, or other reasonable means where required by applicable law.", "Continued use of the Service after the effective date of an updated Privacy Policy constitutes acknowledgment of the updated Privacy Policy."]],
        ["Contact Us", ["Shenzhen Lingxi Zhigan Technology Co., Ltd.", "Product: AlignX", "Website: alignxagent.com", "Email: support@alignxagent.com", "Address: Not set"]],
      ],
    },
    terms: {
      title: "Terms of Service",
      sections: [
        ["Company Information", ["Company Name: Shenzhen Lingxi Zhigan Technology Co., Ltd.", "Product Name: AlignX", "Website: alignxagent.com", "Contact Email: support@alignxagent.com", "Registered Address: Not set"]],
        ["Service Description", ["AlignX is an independent software service designed for Amazon sellers. The Service provides operation validation, ASIN operation records, listing readiness review, advertising budget review, execution tracking, result analysis, and related decision-support functions.", "The Service is intended to assist Users in reviewing operational decisions. The Service does not replace the User's independent business judgment."]],
        ["Independent Service Disclaimer", ["AlignX is an independent software service.", "Unless expressly stated in writing, AlignX is not affiliated with, endorsed by, certified by, authorized by, or officially sponsored by Amazon.", "The use of the term Amazon on the website or within the Service is solely for identification of the marketplace or data source relevant to the User's seller operations."]],
        ["Eligibility And Authority", ["By using the Service, you represent and warrant that you have legal capacity to enter into these Terms, are using the Service for business purposes, have authority to bind any company or organization you represent, have the necessary rights and permissions to submit data and authorize access, and will comply with applicable laws, regulations, platform policies, and contractual obligations."]],
        ["Account Registration", ["Users may be required to create an account to access certain Service functions.", "Users must provide accurate, complete, and current account information.", "Users are responsible for maintaining the confidentiality of their login credentials and for all activities occurring under their accounts.", "Users must promptly notify us of any unauthorized access, security incident, or suspected account compromise."]],
        ["Seller Authorization", ["If a User connects an Amazon seller account or other third-party data source, the User represents and warrants that the User has the authority to grant such authorization.", "AlignX accesses and processes connected data only within the authorized scope and for purposes of providing the requested Service functions.", "The User is responsible for maintaining, modifying, or revoking authorization through the applicable platform settings or by contacting support@alignxagent.com.", "Revocation or disconnection may limit or disable certain Service functions."]],
        ["No Seller Central Password Collection", ["AlignX does not ask Users to provide their Amazon Seller Central password.", "Users must not submit Seller Central passwords to AlignX through forms, support messages, emails, files, or any other channel.", "If a User accidentally submits such credentials, the User must change the relevant credentials immediately and notify us."]],
        ["User Responsibilities", ["Users are solely responsible for their own business decisions, the accuracy, legality, and completeness of submitted data, the authority to connect accounts and authorize data access, compliance with Amazon policies, marketplace rules, and applicable laws, review and verification of Service outputs, maintaining secure access to their own accounts, devices, systems, and credentials, and ensuring that use of the Service is appropriate for their business circumstances."]],
        ["Prohibited Uses", ["Users must not use the Service to manipulate marketplace ranking, search results, product reviews, ratings, feedback, or customer behavior.", "Users must not engage in review manipulation, fake orders, fake traffic, fake clicks, fake engagement, or other deceptive conduct.", "Users must not scrape, collect, or access Amazon data without authorization.", "Users must not bypass, disable, interfere with, or circumvent Amazon authorization mechanisms, security controls, access controls, rate limits, or technical restrictions.", "Users must not misuse Seller Data, Amazon Information, buyer data, or third-party data.", "Users must not submit, upload, or process data that the User has no right to use.", "Users must not use the Service for illegal, fraudulent, harmful, abusive, or deceptive activities.", "Users must not reverse engineer, decompile, copy, modify, exploit, or interfere with the Service.", "Users must not perform security attacks, vulnerability probing, load testing, denial-of-service attacks, or unauthorized penetration testing.", "Users must not introduce malware, spyware, viruses, or harmful code.", "Users must not share access credentials without authorization.", "Users must not use the Service in a manner that violates Amazon policies, applicable laws, third-party rights, or these Terms."]],
        ["No Guaranteed Business Results", ["AlignX provides analysis, records, review tools, and decision-support functions.", "We do not guarantee sales growth, ranking improvement, ACOS reduction, conversion rate increase, profit increase, advertising performance improvement, inventory turnover improvement, marketplace approval, account performance improvement, or any specific business outcome.", "All business decisions remain the sole responsibility of the User."]],
        ["Service Outputs", ["The Service may generate analysis, recommendations, reports, records, scores, summaries, explanations, or other outputs.", "Service outputs are provided for informational and decision-support purposes only.", "Users must independently review, verify, and evaluate all outputs before taking action.", "We do not represent that any output is complete, error-free, suitable for every circumstance, compliant with every marketplace policy, or legally sufficient for any particular purpose."]],
        ["Data And Privacy", ["Our collection, use, storage, protection, disclosure, and deletion of data are governed by our Privacy Policy and any applicable Data Use Policy.", "By using the Service, you acknowledge and agree that we may process data as described in those policies."]],
        ["Amazon Information", ["If the Service processes Amazon Information, such processing will be subject to applicable authorization, Amazon policies, contractual obligations, data protection requirements, and the User's authorized use case.", "Users must not use AlignX to obtain, process, or disclose Amazon Information in violation of Amazon policies, applicable law, third-party rights, or these Terms."]],
        ["Fees And Payment", ["Certain Service functions may be offered for a fee.", "Fees, billing cycles, payment methods, refund rules, and subscription terms will be displayed separately or agreed in writing.", "Users are responsible for all applicable taxes, duties, charges, or fees arising from the purchase or use of paid services.", "Failure to pay fees may result in suspension, limitation, or termination of paid Service functions."]],
        ["Service Availability", ["We may modify, update, suspend, restrict, or discontinue all or part of the Service at any time.", "We do not guarantee uninterrupted, error-free, secure, or always-available operation of the Service.", "The Service may be unavailable due to maintenance, updates, outages, third-party service failures, security events, force majeure, or other reasons."]],
        ["Third-Party Services", ["The Service may integrate with or link to third-party services, platforms, APIs, tools, websites, hosting providers, payment providers, or data sources.", "We are not responsible for third-party services, third-party policies, third-party outages, third-party data accuracy, or third-party actions.", "Use of third-party services may be subject to separate terms and policies."]],
        ["Intellectual Property", ["The Service, website, software, user interface, design, trademarks, logos, content, documentation, code, systems, workflows, models, databases, and related materials are owned by or licensed to the Company and are protected by applicable intellectual property laws.", "Except as expressly permitted, Users may not copy, reproduce, modify, distribute, sell, lease, sublicense, reverse engineer, or create derivative works based on the Service."]],
        ["User Data Ownership", ["As between the User and the Company, the User retains ownership of data lawfully submitted by the User or lawfully authorized by the User for processing through the Service.", "The User grants the Company a limited, non-exclusive, worldwide right to access, process, store, transmit, analyze, and use such data solely to provide, secure, maintain, improve, and support the Service, subject to the Privacy Policy and applicable law."]],
        ["Confidentiality", ["Each party may receive non-public information from the other party.", "The receiving party must use reasonable care to protect confidential information and must not disclose it except as necessary to perform obligations, provide the Service, comply with law, or enforce rights."]],
        ["Security", ["We implement reasonable technical and organizational measures designed to protect the Service and data.", "Users are responsible for maintaining the security of their own accounts, systems, devices, networks, and credentials.", "Users must promptly notify us of any suspected security incident involving the Service."]],
        ["Suspension And Termination", ["We may suspend, restrict, or terminate access to the Service if the User violates these Terms, applicable law, or platform policy, creates security, legal, operational, or reputational risk, fails to satisfy payment obligations, may harm the Service, other users, third parties, or the Company, or where required by law, regulation, court order, platform requirement, or government authority.", "Users may stop using the Service at any time.", "Termination does not affect rights and obligations that by their nature should survive, including payment obligations, confidentiality, intellectual property, disclaimers, limitation of liability, indemnity, data retention, and dispute resolution provisions."]],
        ["Disclaimers", ["To the maximum extent permitted by applicable law, the Service is provided on an as is and as available basis.", "We disclaim all warranties, express, implied, statutory, or otherwise, including warranties of merchantability, fitness for a particular purpose, title, non-infringement, accuracy, availability, security, reliability, and error-free operation.", "We do not warrant that the Service will meet the User's requirements, achieve specific results, prevent business losses, or ensure compliance with every marketplace policy or legal obligation."]],
        ["Limitation Of Liability", ["To the maximum extent permitted by applicable law, the Company, its affiliates, officers, directors, employees, contractors, agents, licensors, and service providers shall not be liable for any indirect, incidental, special, consequential, exemplary, or punitive damages, or for loss of profits, revenue, goodwill, data, business opportunities, or anticipated savings.", "To the maximum extent permitted by applicable law, the Company's total liability arising out of or relating to the Service or these Terms shall not exceed the amount paid by the User to the Company for the Service during the three months immediately preceding the event giving rise to the claim, or USD 100, whichever is greater.", "Some jurisdictions do not allow certain limitations of liability. In such jurisdictions, liability shall be limited to the maximum extent permitted by law."]],
        ["Indemnification", ["Users agree to defend, indemnify, and hold harmless the Company, its affiliates, officers, directors, employees, contractors, agents, licensors, and service providers from and against claims, damages, liabilities, losses, costs, and expenses, including reasonable attorneys' fees, arising out of or relating to the User's use of the Service, violation of these Terms, violation of applicable law, platform policy, or third-party rights, data submitted, authorized, or processed by the User, business decisions made by the User based on Service outputs, or unauthorized account access caused by the User's failure to protect credentials."]],
        ["Changes To The Service Or Terms", ["We may update these Terms from time to time.", "The updated Terms will be posted on this page with an updated effective date.", "Material changes may be notified through the Service, email, or other reasonable means where required by law.", "Continued use of the Service after the effective date of updated Terms constitutes acceptance of the updated Terms."]],
        ["Governing Law", ["Governing law jurisdiction: Not set."]],
        ["Dispute Resolution", ["Dispute resolution method and venue: Not set.", "If no dispute resolution method is specified, the parties shall first attempt to resolve the dispute through good-faith negotiation."]],
        ["Force Majeure", ["We shall not be liable for any delay or failure to perform caused by events beyond our reasonable control, including natural disasters, war, terrorism, civil unrest, labor disputes, government actions, power failures, internet failures, cyberattacks, third-party service failures, platform outages, regulatory changes, or other force majeure events."]],
        ["Severability", ["If any provision of these Terms is found invalid, illegal, or unenforceable, the remaining provisions shall remain in full force and effect."]],
        ["Entire Agreement", ["These Terms, together with the Privacy Policy, Data Use Policy, Security Policy, order forms, and any other policies or agreements incorporated by reference, constitute the entire agreement between the User and the Company regarding the Service."]],
        ["Contact", ["Shenzhen Lingxi Zhigan Technology Co., Ltd.", "Product: AlignX", "Website: alignxagent.com", "Email: support@alignxagent.com", "Address: Not set"]],
      ],
    },
    "data-use-policy": {
      title: "Data Use Policy",
      sections: [
        ["Authorization", ["AlignX accesses seller data only after seller authorization."]],
        ["Data Types", home.en.dataUse],
        ["Purpose", ["Operation validation, ASIN records, listing review, advertising analysis and result tracking."]],
        ["Minimum Necessary Use", ["AlignX uses only data needed for the selected validation workflow."]],
        ["No Seller Central Password", ["AlignX does not ask sellers to share their Seller Central password."]],
        ["Buyer PII", ["AlignX does not need buyer personal information by default."]],
        ["Revocation", ["Sellers can disconnect or revoke access according to authorization settings."]],
        ["Deletion", ["Data deletion requests can be sent to support@alignxagent.com."]],
        ["Security Measures", ["HTTPS, access control, purpose limitation, credential protection, logs and audit controls."]],
      ],
    },
    security: {
      title: "Security",
      sections: [
        ["HTTPS", ["AlignX is provided over HTTPS."]],
        ["Access Control", ["Access is controlled by authenticated accounts and authorization settings."]],
        ["Least Privilege", ["Data access is limited to what is needed for operation validation workflows."]],
        ["Encrypted Transmission", ["Data is transmitted over encrypted connections."]],
        ["Credential Protection", ["Authorization credentials are protected and Seller Central passwords are not collected."]],
        ["Logging And Audit", ["Key service actions may be logged for security, troubleshooting and audit purposes."]],
        ["Incident Response", ["Security events are reviewed and handled according to severity and service impact."]],
        ["Deletion Requests", ["Data deletion requests are handled through support@alignxagent.com."]],
      ],
    },
    contact: {
      title: "Contact",
      sections: [
        ["Company", [company.en]],
        ["Product", ["AlignX"]],
        ["Support Email", ["support@alignxagent.com"]],
        ["Privacy / Data Deletion Requests", ["support@alignxagent.com"]],
      ],
    },
  },
  zh: {
    about: {
      title: "关于 AlignX",
      sections: [
        ["公司名称", [company.zh]],
        ["产品名称", ["AlignX"]],
        ["服务对象", ["需要在投入放大前进行经营验证的 Amazon 卖家。"]],
        ["服务范围", ["产品机会判断、Listing 检查、广告分析、ASIN 记录、执行记录和效果复盘。"]],
        ["数据使用原则", ["仅在卖家授权后，为经营验证、ASIN 记录、Listing 检查、广告分析和效果复盘使用必要数据。"]],
        ["联系方式", ["support@alignxagent.com"]],
        ["免责声明", [labels.zh.disclaimer]],
      ],
    },
    "privacy-policy": {
      title: "隐私政策",
      sections: [
        ["收集哪些信息", ["账号联系信息、服务使用信息、卖家授权数据和支持请求信息。"]],
        ["如何使用", ["用于经营验证、ASIN 记录、Listing 检查、广告分析、效果复盘、支持和安全。"]],
        ["如何存储", ["信息存储在用于提供 AlignX 服务的受控系统中。"]],
        ["如何保护", ["我们使用 HTTPS、访问控制、限定用途、凭证保护、日志和运营安全措施。"]],
        ["是否分享", ["我们不出售卖家数据。仅在提供服务、遵守法律或保护服务所需时共享数据。"]],
        ["数据保留时间", ["数据仅在服务交付、法律义务、审计和安全目的所需期间保留。"]],
        ["如何删除", ["卖家可以通过 support@alignxagent.com 请求删除。"]],
        ["如何联系", ["support@alignxagent.com"]],
        ["地区法规适用说明", ["适用情况下，隐私权利可能因地区而异，并将按适用法律处理。"]],
      ],
    },
    terms: {
      title: "用户协议",
      sections: [
        ["公司与产品", ["本用户协议适用于深圳灵曦智感科技有限公司开发的 AlignX 软件服务。AlignX 面向 Amazon 卖家提供经营投入验证能力。"]],
        ["服务说明", ["AlignX 为 Amazon 卖家提供经营验证、ASIN 经营档案、Listing 承接检查、广告预算复盘、执行记录追踪和效果验证分析服务。"]],
        ["独立服务声明", ["AlignX 是独立软件服务。除非另有明确说明，AlignX 与 Amazon 不存在官方关联、官方背书或官方赞助关系。"]],
        ["账号注册", ["用户应提供真实、准确的账号信息，并妥善保管自己的登录凭证。"]],
        ["卖家授权", ["如果用户连接 Amazon 卖家账号，用户应确保其有权进行该授权。AlignX 仅在授权范围内访问卖家数据。"]],
        ["不收集 Seller Central 密码", ["AlignX 不要求用户提供 Seller Central 登录密码。"]],
        ["用户责任", ["用户应对自身经营决策、提交信息的准确性、遵守 Amazon 政策、遵守适用法律法规和合理使用服务负责。"]],
        ["禁止用途", ["禁止刷排名、操控评论、未授权抓取、绕过 Amazon 授权机制、滥用卖家或买家数据、违法活动、安全攻击、未经授权共享访问凭证。"]],
        ["不保证经营结果", ["AlignX 提供分析和决策支持工具。我们不保证销量增长、排名提升、ACOS 降低、利润增加或任何特定经营结果。"]],
        ["数据与隐私", ["数据使用受《隐私政策》和《数据使用政策》约束。"]],
        ["服务变更", ["我们可能不时更新、修改、暂停或终止部分服务。"]],
        ["终止", ["用户可以随时停止使用服务。如果用户违反本协议，或造成安全、法律、运营风险，我们可以暂停或终止其访问权限。"]],
        ["责任限制", ["在法律允许的最大范围内，AlignX 不对间接、附带、特殊、后果性、惩罚性损失，或利润、收入、数据、商业机会损失承担责任。"]],
        ["联系方式", ["Company: Shenzhen Lingxi Zhigan Technology Co., Ltd.", "Product: AlignX", "Email: support@alignxagent.com"]],
      ],
    },
    "data-use-policy": {
      title: "数据使用政策",
      sections: [
        ["授权方式", ["AlignX 仅在卖家授权后访问卖家数据。"]],
        ["数据类型", home.zh.dataUse],
        ["使用目的", ["经营验证、ASIN 记录、Listing 检查、广告分析和效果复盘。"]],
        ["最小必要原则", ["AlignX 仅使用所选验证流程所需的数据。"]],
        ["不收集 Seller Central 密码", ["AlignX 不要求卖家提供 Seller Central 登录密码。"]],
        ["买家个人信息", ["AlignX 默认不需要买家个人信息。"]],
        ["撤销授权", ["卖家可以根据授权设置断开或撤销访问。"]],
        ["数据删除", ["数据删除请求可发送至 support@alignxagent.com。"]],
        ["安全措施", ["HTTPS、访问控制、限定用途、凭证保护、日志和审计控制。"]],
      ],
    },
    security: {
      title: "安全说明",
      sections: [
        ["HTTPS", ["AlignX 通过 HTTPS 提供服务。"]],
        ["访问控制", ["访问由认证账号和授权设置控制。"]],
        ["最小权限原则", ["数据访问限制在经营验证流程所需范围内。"]],
        ["加密传输", ["数据通过加密连接传输。"]],
        ["凭证保护", ["授权凭证受到保护，不收集 Seller Central 密码。"]],
        ["日志和审计", ["关键服务动作可能用于安全、排障和审计目的而记录。"]],
        ["安全事件响应", ["安全事件会根据严重程度和服务影响进行处理。"]],
        ["数据删除请求处理", ["数据删除请求通过 support@alignxagent.com 处理。"]],
      ],
    },
    contact: {
      title: "联系我们",
      sections: [
        ["公司名称", [company.zh]],
        ["产品名称", ["AlignX"]],
        ["支持邮箱", ["support@alignxagent.com"]],
        ["隐私 / 数据删除请求", ["support@alignxagent.com"]],
      ],
    },
  },
};

export function RootRedirect() {
  return <Navigate to="/en" replace />;
}

export default function PublicSite() {
  const location = useLocation();
  const parts = location.pathname.split("/").filter(Boolean);
  const lang: Lang = parts[0] === "zh" ? "zh" : "en";
  const key = (parts[1] || "home") as PageKey;
  const copy = labels[lang];

  return (
    <div className="min-h-screen bg-[#fbfaf7] text-[#0F2A24]">
      <Header lang={lang} />
      {key === "home" ? <Home lang={lang} /> : <PolicyPage lang={lang} pageKey={key} />}
      <Footer lang={lang} copy={copy} />
    </div>
  );
}

function Header({ lang }: { lang: Lang }) {
  const copy = labels[lang];
  const location = useLocation();
  const currentPage = location.pathname.split("/").filter(Boolean)[1] || "";
  const switchLang: Lang = lang === "en" ? "zh" : "en";
  const switchPath = `/${switchLang}${currentPage ? `/${currentPage}` : ""}`;

  return (
    <header className="sticky top-0 z-20 border-b border-[#0F2A24]/10 bg-[#fbfaf7]/92 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1120px] items-center justify-between px-5">
        <a href={`/${lang}`} className="text-[24px] font-semibold tracking-[-0.04em] text-[#0F2A24]">
          AlignX
        </a>
        <nav className="hidden items-center gap-7 text-[14px] text-[#0F2A24]/70 lg:flex">
          {copy.nav.map((item, index) => {
            const href = copy.paths[index].startsWith("#") ? `/${lang}${copy.paths[index]}` : copy.paths[index];
            return <a key={item} href={href} className="transition-colors hover:text-[#0F2A24]">{item}</a>;
          })}
        </nav>
        <div className="flex items-center gap-3">
          <a href={switchPath} className="hidden text-[13px] text-[#0F2A24]/60 hover:text-[#0F2A24] sm:inline">
            {lang === "en" ? "中文" : "EN"}
          </a>
          <a href="/login" className="rounded-full bg-[#0F2A24] px-4 py-2 text-[14px] font-medium text-white transition-colors hover:bg-[#173a32]">
            {copy.login}
          </a>
        </div>
      </div>
    </header>
  );
}

function Home({ lang }: { lang: Lang }) {
  const h = home[lang];
  return (
    <main>
      <section className="mx-auto grid min-h-[650px] max-w-[1120px] items-center gap-12 px-5 py-20 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <p className="mb-6 text-[15px] font-medium text-[#B18742]">{h.supportLine}</p>
          <h1 className="max-w-[780px] text-[46px] font-semibold leading-[1.04] tracking-[-0.055em] text-[#0F2A24] sm:text-[62px]">
            {h.heroTitle}
          </h1>
          <p className="mt-7 max-w-[700px] text-[20px] leading-[1.55] tracking-[-0.03em] text-[#0F2A24]/75">
            {h.heroSubtitle}
          </p>
        </div>
        <div className="rounded-[28px] border border-[#0F2A24]/12 bg-white p-6 shadow-[0_24px_80px_rgba(15,42,36,0.10)]">
          <p className="mb-5 text-[14px] font-semibold text-[#0F2A24]">{h.cardTitle}</p>
          <div className="space-y-4">
            {h.card.map(([label, value]) => <InfoLine key={label} label={label} value={value} />)}
          </div>
        </div>
      </section>

      <TextSection id="why" title={h.painTitle} lines={h.painBody} close={h.painClose} />

      <section id="how" className="border-t border-[#0F2A24]/8 bg-white">
        <div className="mx-auto max-w-[1020px] px-5 py-24">
          <h2 className="text-[36px] font-semibold tracking-[-0.045em]">{h.helpTitle}</h2>
          <div className="mt-10 grid gap-4 md:grid-cols-2">
            {h.helpCards.map(([title, text]) => <SimpleCard key={title} title={title} text={text} />)}
          </div>
        </div>
      </section>

      <section className="border-t border-[#0F2A24]/8">
        <div className="mx-auto max-w-[1020px] px-5 py-24">
          <h2 className="max-w-[780px] text-[36px] font-semibold tracking-[-0.045em]">{h.dataTitle}</h2>
          <p className="mt-6 max-w-[820px] text-[17px] leading-[1.8] text-[#0F2A24]/68">{h.dataBody}</p>
          <div className="mt-10 grid gap-5 md:grid-cols-2">
            <ListBlock title={h.dataUseTitle} items={h.dataUse} />
            <ListBlock title={h.dataNoTitle} items={h.dataNo} />
          </div>
        </div>
      </section>

      <section id="security" className="border-t border-[#0F2A24]/8 bg-white">
        <div className="mx-auto max-w-[1020px] px-5 py-24">
          <h2 className="max-w-[780px] text-[36px] font-semibold tracking-[-0.045em]">{h.securityTitle}</h2>
          <div className="mt-10 grid gap-4 md:grid-cols-2">
            {h.securityCards.map(([title, text]) => <SimpleCard key={title} title={title} text={text} />)}
          </div>
        </div>
      </section>

      <section className="border-t border-[#0F2A24]/8">
        <div className="mx-auto max-w-[960px] px-5 py-24">
          <h2 className="text-[36px] font-semibold tracking-[-0.045em]">{h.aboutTitle}</h2>
          <div className="mt-8 space-y-4 text-[17px] leading-[1.8] text-[#0F2A24]/70">
            {h.aboutBody.map((line) => <p key={line}>{line}</p>)}
          </div>
          <div className="mt-10 grid gap-3 md:grid-cols-2">
            {h.aboutFacts.map(([label, value]) => <InfoLine key={label} label={label} value={value} />)}
          </div>
          <p className="mt-8 text-[14px] leading-[1.7] text-[#0F2A24]/60">{labels[lang].disclaimer}</p>
        </div>
      </section>

      <section className="border-t border-[#0F2A24]/8 bg-white">
        <div className="mx-auto max-w-[980px] px-5 py-24">
          <h2 className="text-[36px] font-semibold tracking-[-0.045em]">{h.usersTitle}</h2>
          <div className="mt-9 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {h.users.map((item) => (
              <div key={item} className="rounded-2xl border border-[#0F2A24]/10 bg-[#fbfaf7] p-5 text-[15px] font-medium text-[#0F2A24]/78">
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

function TextSection({ id, title, lines, close }: { id: string; title: string; lines: string[]; close: string }) {
  return (
    <section id={id} className="border-t border-[#0F2A24]/8">
      <div className="mx-auto max-w-[900px] px-5 py-24">
        <h2 className="text-[36px] font-semibold tracking-[-0.045em] text-[#0F2A24]">{title}</h2>
        <div className="mt-8 space-y-3 text-[19px] leading-[1.75] text-[#0F2A24]/72">
          {lines.map((line) => <p key={line}>{line}</p>)}
        </div>
        <p className="mt-10 max-w-[760px] text-[24px] font-medium leading-[1.45] tracking-[-0.035em] text-[#0F2A24]">{close}</p>
      </div>
    </section>
  );
}

function PolicyPage({ lang, pageKey }: { lang: Lang; pageKey: PageKey }) {
  const page = pages[lang][pageKey as Exclude<PageKey, "home">];
  if (!page) return <Navigate to={`/${lang}`} replace />;
  return (
    <main className="mx-auto max-w-[940px] px-5 py-20">
      <h1 className="text-[44px] font-semibold tracking-[-0.05em] text-[#0F2A24]">{page.title}</h1>
      <p className="mt-4 text-[14px] text-[#0F2A24]/55">
        {lang === "en" ? `Effective Date: ${effectiveDate}` : `生效日期：${effectiveDate}`}
      </p>
      <div className="mt-12 space-y-6">
        {page.sections.map(([title, lines]) => (
          <section key={title} className="rounded-2xl border border-[#0F2A24]/10 bg-white p-6">
            <h2 className="text-[18px] font-semibold tracking-[-0.03em]">{title}</h2>
            <div className="mt-4 space-y-2 text-[15px] leading-[1.75] text-[#0F2A24]/70">
              {lines.map((line) => <p key={line}>{line}</p>)}
            </div>
          </section>
        ))}
      </div>
      {pageKey === "contact" && <ContactForm lang={lang} />}
    </main>
  );
}

function ContactForm({ lang }: { lang: Lang }) {
  const isEn = lang === "en";
  return (
    <section className="mt-6 rounded-2xl border border-[#0F2A24]/10 bg-white p-6">
      <h2 className="text-[18px] font-semibold tracking-[-0.03em]">{isEn ? "Contact Form" : "联系表单"}</h2>
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <input className="apple-input" placeholder={isEn ? "Name" : "姓名"} />
        <input className="apple-input" placeholder={isEn ? "Email" : "邮箱"} />
        <textarea className="apple-input min-h-[120px] md:col-span-2" placeholder={isEn ? "Message" : "留言"} />
      </div>
      <a
        href="mailto:support@alignxagent.com"
        className="mt-5 inline-flex rounded-full bg-[#0F2A24] px-5 py-2.5 text-[14px] font-medium text-white"
      >
        {isEn ? "Send To Support" : "发送给支持邮箱"}
      </a>
    </section>
  );
}

function Footer({ lang, copy }: { lang: Lang; copy: typeof labels.en }) {
  return (
    <footer className="border-t border-[#0F2A24]/10">
      <div className="mx-auto max-w-[1120px] px-5 py-10">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-[20px] font-semibold tracking-[-0.04em] text-[#0F2A24]">AlignX</p>
            <p className="mt-2 text-[14px] text-[#0F2A24]/60">{copy.footerValue}</p>
            <p className="text-[14px] text-[#0F2A24]/60">{copy.method}</p>
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-2 text-[14px] text-[#0F2A24]/64">
            {copy.footerLinks.map(([label, href]) => <a key={href} href={href} className="hover:text-[#0F2A24]">{label}</a>)}
          </div>
        </div>
        <p className="mt-8 max-w-[900px] text-[12px] leading-[1.6] text-[#0F2A24]/48">{copy.disclaimer}</p>
        <p className="mt-3 text-[12px] text-[#0F2A24]/40">{lang === "en" ? company.en : company.zh}</p>
      </div>
    </footer>
  );
}

function InfoLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-[#0F2A24]/[0.035] p-4">
      <p className="text-[12px] text-[#0F2A24]/45">{label}</p>
      <p className="mt-1 text-[16px] font-medium tracking-[-0.03em] text-[#0F2A24]">{value}</p>
    </div>
  );
}

function SimpleCard({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl border border-[#0F2A24]/10 bg-[#fbfaf7] p-6">
      <p className="text-[18px] font-semibold tracking-[-0.03em]">{title}</p>
      <p className="mt-4 text-[15px] leading-[1.7] text-[#0F2A24]/65">{text}</p>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-[#0F2A24]/10 bg-white p-6">
      <p className="text-[18px] font-semibold tracking-[-0.03em]">{title}</p>
      <ul className="mt-5 space-y-3 text-[15px] leading-[1.7] text-[#0F2A24]/68">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}
