---
title: "Rubber Stamped: Forging SPF and DMARC to send mail as any Gmail or G Suite customer"
date: 2020-08-01T00:00:00+00:00
author: "Allison Husain"
tags: ["security", "web"]
showFullContent: false
---

Due to missing verification when configuring mail routes, both Gmail's and any G Suite customer's strict DMARC/SPF policy may be subverted by using G Suite's mail routing rules to relay and grant authenticity to fraudulent messages. This is notably *not* the same as [classic mail spoofing](https://en.wikipedia.org/wiki/Email_spoofing) of yesteryear in which the `From` header is given an arbitrary value, a technique which is easily blocked by mail servers using the [Sender Policy Framework (SPF)](https://en.wikipedia.org/wiki/Sender_Policy_Framework) and [Domain-based Message Authentication, Reporting and Conformance (DMARC)](https://en.wikipedia.org/wiki/DMARC). This issue is a bug unique to Google which allows an attacker to send mail as any other user or G Suite customer **while still passing even the most restrictive SPF and DMARC rules.** 


## A quick detour into mail spoofing

If you're already familiar with both SPF and DMARC, feel free to skip ahead!

Email is *ancient* technology-wise and comes from an era where the internet was nothing more than research universities and government labs. This was a point in time where if someone was misusing a computer, you'd be able to call them or their supervisor and personally tell them off. As the internet grew and more adversaries found their way online, however, very trusting and insecure systems like email needed to evolve.

One of email's growing pains was that both the content and sender of messages are entirely unauthenticated by default. This means that when a message was received by a mail server, there was no clear way to be sure that the message actually originated from the address it claims. In other words, anyone at all could claim they have a message from `the-president@whitehouse.gov` and mail servers would have few formal or rigorous means to call their bluff. This of course was an enormous problem due to phishing and scams as users, for better or for worse, trust and rely on email domains to be sure they're talking to who they think they are.

**Enter SPF and DMARC**

The solution to this problem was to bolt on new controls which would allow the operator of a domain to inform mail servers which IP addresses are allowed to send mail from their domain. This allows administrators to give receiving mail servers the tools they need to confidently call a sender's bluff because they are now able to compare the sender's IP address (which, due to email using TCP, cannot be forged) against the authorized senders list. If the sender's IP isn't on the list, the mail server can confidently reject the message and prevent fraudulent email from hitting its users' inboxes.

The key takeaway with this protection, which will be important to this bug, is that SPF and DMARC use a sender's IP to protect against spoofed and fraudulent messages. This is to say that **if the message originates from an approved source, it is considered legitimate under SPF and DMARC**. 


## The Bug

While poking around on the G Suite administrator console, I noticed I could create global mail routing rules for inbound mail on my domain using the "Default routing" option under "Settings for Gmail". These rules allowed me to, among other things, apply custom headers, modify the subject line, or change the who the email should be sent to before it is processed by the rest of Google's infrastructure.

<center>
<img src="/images/003_gsuite_spf_bypass/Envelope_Rewriting.png"style="max-height: 480px; max-width: 100%; height: auto; width: auto;"/>
</center>

This last option, show above as "Change envelope recipient", was especially interesting because it let me specify an arbitrary recipient and cause Google's backend to resend the email to someone else. Worryingly, the recipient value is accepted by G Suite without performing any validation to ensure that I own either the destination email address or the destination domain. This behavior immediately set off alarm bells in my head as I thought back to SPF and DMARC because this buggy feature would let me redirect incoming emails, including spoofed emails, to someone else *using Google's backend so that it no longer appears to be spoofed according to SPF and DMARC* if the victim also designates Google as an approved sender!

(Un)fortunately, this initial procedure of sending a spoofed email through routing rules didn't entirely work. While I was able to successfully get Google's backend to redirect and redeliver spoofed emails using domains which either didn't have SPF/DMARC or employed a weaker `soft-fail`/`quarantine` policy, I discovered that domains which used DMARC's hardened `reject` policy failed to deliver because my spoofed emails were being dropped at Google's border mail servers due to SPF/DMARC enforcement. This was rather disappointing because most targets who are worth impersonating use `p=reject` and so would seem not vulnerable. Was this *the end of my journey, the culmination of my perilous quest*? Fear not, dear reader, it was not!

In all seriousness, the workaround for this issue wasn't terribly complicated. By digging around in the G Suite admin panel a bit more, I found a section to configure what Google called an "inbound gateway" for my domain. [Google provides a succinct explanation of this feature in their docs](https://support.google.com/a/answer/60730?hl=en) (emphasis mine):

>An inbound mail gateway is a server that all your incoming mail passes through. The gateway typically processes the mail in some way, such as archiving it or filtering spam. It then passes the mail to the mail server that delivers the mail to recipients.
>
> [...]
> 
> You configure the inbound gateway setting to identify the gateway’s IP address or range of addresses. **Gmail skips performing SPF checks on IP addresses included in the Gateway IPs list. If an inbound gateway is set up, the DMARC check should be done by the inbound gateway and will be skipped for messages arriving from listed hosts.**

The final note on SPF and DMARC with inbound gateways was just what I was looking for. This is because it would allow me to inject messages which would otherwise be flat out rejected due to SPF and DMARC failures (such as spoofed messages) into Google's mail infrastructure and, consequently, have them be processed by my custom mail routing rules.

![Attack diagram](/images/003_gsuite_spf_bypass/Attack_Diagram.svg)

By chaining together both the broken recipient validation in G Suite's mail validation rules and an inbound gateway, I was able to cause Google's backend to resend mail for any domain which was clearly spoofed when it was received. This is advantageous for an attacker if the the victim they intend to impersonate *also* uses Gmail or G Suite because it means *the message sent by Google's backend will pass both SPF and DMARC* as their domain will, by nature of using G Suite, be configured to allow Google's backend to send mail from their domain. Additionally, since the message is originating from Google's backend, it is also likely that the message will have a lower spam score and so should be filtered less often.

## Proof of Concept

In this proof of concept, I am using my personal G Suite domain (`mail-relay@ezh.es`) to send a seemingly legitimate email from a `google.com` address to university's G Suite email on a domain which I do not control (`test@berkeley.edu`). I chose to send to another G Suite account to demonstrate that Google's strong mail filtering and anti-spam techniques do not block or detect this attack. Additionally, I chose to impersonate `google.com` because their DMARC policy is set to `p=reject` and so [any violations of SPF (regardless of the SPF policy) should result in the message simply being dropped with prejudice.](https://serverfault.com/a/945817/417964)

The following is a slightly cleaned up email from the end victim's perspective with various irrelevant headers removed to improve readability:

```yaml
Delivered-To: test@berkeley.edu
Received: by 2002:a05:6830:1db6:0:0:0:0 with SMTP id z22csp1120956oti;
        Fri, 3 Apr 2020 15:41:27 -0700 (PDT)
X-Received: by 2002:a17:90b:915:: with SMTP id bo21mr10227430pjb.58.1585953687701;
        Fri, 03 Apr 2020 15:41:27 -0700 (PDT)
ARC-Authentication-Results: i=2; mx.google.com;
       arc=pass (i=1);
       spf=pass (google.com: domain of not_malicious_security_research@google.com designates 209.85.220.69 as permitted sender) smtp.mailfrom=not_malicious_security_research@google.com;
       dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=google.com
Return-Path: <not_malicious_security_research@google.com>
Received: from mail-sor-f69.google.com (mail-sor-f69.google.com. [209.85.220.69])
        by mx.google.com with SMTPS id o11sor13151518plk.43.2020.04.03.15.41.27
        for <test@berkeley.edu>
        (Google Transport Security);
        Fri, 03 Apr 2020 15:41:27 -0700 (PDT)
Received-SPF: pass (google.com: domain of not_malicious_security_research@google.com designates 209.85.220.69 as permitted sender) client-ip=209.85.220.69;
Authentication-Results: mx.google.com;
       arc=pass (i=1);
       spf=pass (google.com: domain of not_malicious_security_research@google.com designates 209.85.220.69 as permitted sender) smtp.mailfrom=not_malicious_security_research@google.com;
       dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=google.com
X-Original-Authentication-Results: mx.google.com;
       spf=softfail (google.com: domain of transitioning not_malicious_security_research@google.com does not designate 64.90.62.162 as permitted sender) smtp.mailfrom=not_malicious_security_research@google.com
X-Received: by 2002:a17:902:690b:: with SMTP id j11mr3579141plk.236.1585953687402;
        Fri, 03 Apr 2020 15:41:27 -0700 (PDT)
ARC-Authentication-Results: i=1; mx.google.com;
       spf=softfail (google.com: domain of transitioning not_malicious_security_research@google.com does not designate 64.90.62.162 as permitted sender) smtp.mailfrom=not_malicious_security_research@google.com
Return-Path: <not_malicious_security_research@google.com>
Received: from chocolate.birch.relay.mailchannels.net (chocolate.birch.relay.mailchannels.net. [23.83.209.35])
        by mx.google.com with ESMTPS id s12si7121157pgq.251.2020.04.03.15.41.26
        for <mail-relay@ezh.es>
        (version=TLS1_2 cipher=ECDHE-RSA-AES128-GCM-SHA256 bits=128/128);
        Fri, 03 Apr 2020 15:41:26 -0700 (PDT)
Received-SPF: softfail (google.com: domain of transitioning not_malicious_security_research@google.com does not designate 64.90.62.162 as permitted sender) client-ip=64.90.62.162;
X-Sender-Id: dreamhost|x-authsender|not_malicious_security_research@google.com
Received: from relay.mailchannels.net (localhost [127.0.0.1]) by relay.mailchannels.net (Postfix) with ESMTP id 574F47E11C3 for <mail-relay@ezh.es>; Fri,
  3 Apr 2020 22:41:26 +0000 (UTC)
From: not_malicious_security_research@google.com
Content-Type: text/plain; charset=us-ascii
Content-Transfer-Encoding: 7bit
Mime-Version: 1.0 (Mac OS X Mail 13.4 \(3608.80.23.2.2\))
Date: Fri, 3 Apr 2020 16:41:24 -0600
Subject: Google Bounce Test
Message-Id: <500D88E3-670F-4F8C-BF72-452197BCADE9@google.com>
X-Mailer: Apple Mail (2.3608.80.23.2.2)
    
Hey this is a spoofed email!
```

The first notable header in this message is Google's debug ARC analysis of the message when it was received for the first time from the inbound gateway at the attacker's relay address (`mail-relay@ezh.es`) where it detected the SPF and DMARC failure but did not act on it due to the inbound gateway configuration:

```yaml
ARC-Authentication-Results: i=1; mx.google.com;
       spf=softfail (google.com: domain of transitioning not_malicious_security_research@google.com does not designate 64.90.62.162 as permitted sender) smtp.mailfrom=not_malicious_security_research@google.com
```

The second is when the victim (`test@berkeley.edu`) receives the message and Google re-evaluates the message and determines that both SPF and DMARC pass with the strict `p=REJECT` policy:

```yaml
Authentication-Results: mx.google.com;
       arc=pass (i=1);
       spf=pass (google.com: domain of not_malicious_security_research@google.com designates 209.85.220.69 as permitted sender) smtp.mailfrom=not_malicious_security_research@google.com;
       dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=google.com
```

This results in a completely illegitimate message from a highly trusted domain with strong SPF and DMARC configurations being delivered directly to the victim's inbox without any sort of warning:

<center>
<img src="/images/003_gsuite_spf_bypass/inbox_example.png" style="max-height: 155px; max-width: 100%; height: auto; width: auto;"/>
</center>

<br/>

<center>
<img src="/images/003_gsuite_spf_bypass/gmail_pass_results.png" style="max-height: 406 px; max-width: 100%; height: auto; width: auto;"/>
</center>


## Timeline

* April 1st, 2020 — Initial discovery
* April 3rd, 2020 — Issue reported to Google
* April 16th, 2020 — Google accepts the issue, classifies it as priority 2, severity 2
* April 21st, 2020 — Google marks issue as duplicate
* August 1st, 2020 — **No evidence of progress or attempted mitigations, issue is still reproducible using the same techniques communicated to Google 120 days earlier**. 
* August 1st, 2020 - Google is notified of intent to publish.


