# Failure cases (practice, enc_a top-20, RRF c=0)

For each case fill in **category** (e.g. wording mismatch / name or acronym / ASR form / vague query / near-duplicate docs / bad gold) and a one-line **why**.

| group | n |
| --- | --- |
| rerank: broken (enc_a hit@10 -> miss) | 13 |
| rerank: rescued (enc_a miss@10 -> hit) | 21 |
| rrf: broken (enc_a hit@10 -> miss) | 3 |
| rrf: rescued (enc_a miss@10 -> hit) | 17 |

## Category legend

Each category gives the main reason a query's gold doc moved across the top-10 boundary.
"ASR form: yes/no" is recorded separately, as a secondary factor.

### Broken: why the reranker pushed the gold doc out of the top 10

Not reranker errors (evaluation or query issues):
- plausible alternative: the reranker's top doc also answers the query, but only the gold doc is labelled
- ambiguous query: the query has two clear readings, and the gold doc matches only one
- vague query: the query lacks context that the gold doc relies on

Reranker errors:
- wording mismatch: the gold doc answers in different words or domain jargon, and the reranker does not link them
- same-topic distractor: the reranker's top doc is on the same topic but does not answer the query
- keyword distractor: the reranker's top doc only shares a keyword (often a name) with the query
- ASR form: an acronym or number spelled out by the ASR prevents the match

### Rescued: why the reranker found the gold doc that enc_a missed

Reranker strengths:
- links different wording: the gold doc answers in different words or terms, and the reranker connects them to the query
- matches a key condition in a long query: the query has several parts, and the reranker matches the decisive one
- finds the specific question among similar docs: many docs share the topic, and the reranker picks the one that answers what was asked
- matches a key phrase: the gold doc repeats a phrase from the query that enc_a's single vector underweights

## rerank: broken (enc_a hit@10 -> miss)

### q_ea0be00eda6ea088
- transcript: "Factors influencing the initial stock price at market opening."
- gold rank (top-20): enc_a 5 | rerank 13 | rrf 7
- gold `r_ced0f0a1cac151f1`: When a stock is going to become public there's a level of analysis required to figure out the range of IPO price that makes sense. For a company that's somewhat mature, and has a sector to compare it to, you can come up with a range that would be pretty close. For the recent linkedin, it's tougher t…
- rerank top-1 `r_06012f37ce8a1fdc`: You may simply be asking why stocks 'gap up' or 'gap down' when the stock market opens. This is because the price adjusts to news that occurred while the exchanges were closed overnight. Perhaps Asian stocks crashed, or perhaps a news story was released in the New York Times about some major company…
- category: ambiguous query
- why: "initial stock price at market opening" can mean IPO pricing (gold) or the daily open; the reranker picked the literal daily-open reading ("market opens"), while enc_a kept the IPO doc at rank 5

### q_90c19079b88bb39e
- transcript: "Is the B A A V O's Visa Airline Rewards Card a good option?"
- gold rank (top-20): enc_a 2 | rerank 18 | rrf 3
- gold `r_b743717aa71f452b`: "I am a proud member of the BA frequent fliers' club (Executive Club). Their service is superb. Their avios (aka miles) are quite useful. However, that is if you're not flying with British Airways, because if you do - you'll pay enormous amounts as ""taxes"". I've used their avios on Air Berlin, Ame…
- rerank top-1 `r_101bf36a3c2101a4`: They are not as good of an option when compared to a card you open chosen based on features and rates. Get a card with a lower rate that can be used anywhere.
- category: ASR spelled-out name
- why: "BA Avios" is transcribed as letters "B A A V O", so the reranker cannot match it to "BA"/"avios" in the gold doc and prefers a generic card answer that echoes "a good option"; enc_a ranks gold 2, RRF keeps it at 3

### q_890a6df9ce937b08 [EXAMPLE: RRF FAILS]
- transcript: "How can I determine the exact time a SWIFT is issued by a bank?"
- gold rank (top-20): enc_a 10 | rerank 12 | rrf 11
- gold `r_c4b0886ff3312f06`: I think technically the MIR includes the date of issuance but not the time, see the references here. What you have there looks like a timestamp followed by the MIR. If you look at this example from IBM they also show the input time as a separate field.
- rerank top-1 `r_c1dc72a1adb0e960`: No. You can initiate SWIFT payments from Bank A, whenever Bank A is open for business. The transaction takes around 2-5 days for it to complete depending on the currency pair and countries involved. Once you initiate the payment, the Bank A sends it to SWIFT Network which in turn send it to Bank B. …
- category: wording mismatch
- why: the gold doc answers the question in SWIFT message terms (MIR has the date, input time is a separate field) without the words "issued"/"exact time"; the reranker prefers a doc on SWIFT transfer timing (2–5 days) that shares surface words but answers a different question

### q_90caf2950d97119c
- transcript: "How do I file taxes for the sale of stocks from Form Ten Ninety Nine B?"
- gold rank (top-20): enc_a 3 | rerank 17 | rrf 6
- gold `r_eccd8865b96124a4`: "You can group your like-kind (same symbol, ST/LT) stock positions, just be sure that your totals match the total dollar amounts on the 1099. An inconsistency will possibly result in a letter from IRS to clarify. So, if you sold the 100 shares, and they came from 7 different buys, list it once. The …
- rerank top-1 `r_558333702976f73f`: It is perfectly legitimate to adjust your 1099-B income by broker's fees. Publication 17 (p 116) specifically instructs taxpayers to adjust their Schedule D reporting by broker's fees: Form 1099-B transactions. If you sold property, such as stocks, bonds, or certain commodities, through a broker, yo…
- category: plausible alternative
- why: the reranker's top doc also explains how to report 1099-B stock sales (Schedule D, broker fees) and matches the query's terms more closely ("Form 1099-B", "sold stocks"); the gold answers a different aspect (grouping lots). ASR also writes "1099-B" as "Ten Ninety Nine B"

### q_0b007d68bef85089
- transcript: "What is the impact of a higher A P R on my debt consolidation?"
- gold rank (top-20): enc_a 7 | rerank 13 | rrf 9
- gold `r_ebec6be8b1013529`: No, it means that each year (Annual Payment Rate) you are accruing interest at 29.8%. If your principal is $10,000, that means you are gaining $3,000 of debt per year in addition to this, excluding payments you make/interest on interest.
- rerank top-1 `r_af3f18b2c7b98501`: The debt on Credit Cards is pretty high. Its in the range of 30-40% APR. There could also be a case very high personal loan for medical or other personal emergencies at a rate in excess of 15%. The debt consolidation would offer this at a very low APR There are institutions that offer debt consolida…
- category: plausible alterntaive
- why: the gold doc only explains what an APR means and never mentions debt consolidation; the reranker's top doc covers both APR and debt consolidation, so it fits the query at least as well. ASR also spells "APR" as "A P R"

### q_cef689c374316c83
- transcript: "How to value a small business for investment purposes."
- gold rank (top-20): enc_a 4 | rerank 13 | rrf 6
- gold `r_24b879f9143b05b7`: "It should be pretty obvious that without knowing what sort of assets the company owns, and what sort of net earnings are being generated it's impossible to say what a $20k equity investment should get you in terms of ownership percentage. With that said, you want to look at a few to several years o…
- rerank top-1 `r_69ef643b8e6f9e8b`: There are many ways to value a business. Here is a simple method to get a ball park number on most businesses. This business is made of two parts. For the real estate: For the business: I would consider this type of small business riskier than the stock market and so you should expect a higher retur…
- category: plausible alternative
- why: the gold answers a specific case (what $20k of equity should buy);the reranker's top doc directly explains how to value a small business (two parts, expected return), matching the query almost word for word. Both are reasonable answers.

### q_cbb4c2670652d081 [EXAMPLE: RRF FAILS]
- transcript: "I am thirty years old and have saved thirty thousand dollars. What should I do with it?"
- gold rank (top-20): enc_a 5 | rerank 19 | rrf 11
- gold `r_cf8cc96996d99cab`: "First, two preliminaries, to address good points people made in comments. As AbraCadaver noted, before you move your $30k to something that might lose money, make sure you have enough cash to serve as an emergency fund in case you lose your income. Especially remember that big stock market crashes …
- rerank top-1 `r_59206e0770748944`: "First of all, kudos for thinking about budgeting at 21 years old. So many people don't plan with their money, and years later wonder where it all went. You are doing a lot of things right with your budget. You've got saving goals, namely your next car and a down payment on a house. You are saving a…
- category: same-topic disctractor
- why: the gold doc answers what to do with the $30k (keep an emergency fund first) but opens with replies to comments; the reranker's top doc is generic budgeting advice for a 21-year-old and never says what to do with the money; the reranker matches surface features (young saver, savings goals) and cannot link "thirty thousand dollars" to "$30k"

### q_77403f5d45418ead
- transcript: "U.S. Basics of Stock Taxation."
- gold rank (top-20): enc_a 7 | rerank 11 | rrf 9
- gold `r_ff9022b9dc51d33f`: E.g. I buy 1 stock unit for $100.00 and sell it later for $150.00 => income taxes arise. Correct. You pay tax on your gains, i.e.: the different between net proceeds and gross costs (proceeds sans fees, acquisition costs including fees). I buy 1 stock unit for $150.00 and sell it later for $100.00 =…
- rerank top-1 `r_800022095f385cc7`: If you are a US citizen, you need to very carefully research the US tax implications of investing in foreign stocks before you do so. The US tax rules have been set up in general to make this very unattractive.
- category: same-topic distractor
- why: the gold doc explains the basics with a worked example (tax on gains, losses) but never mentions the U.S.; the reranker's top doc is about U.S. tax on foreign stocks, a narrow special case rather than the basics; the reranker is drawn by the literal match on "U.S." and "tax", helped by the title-like, vague query

### q_23396524ffa342fe [EXAMPLE: RRF RESCUES]
- transcript: "How does Walmart account for expired food inventory?"
- gold rank (top-20): enc_a 1 | rerank 12 | rrf 2
- gold `r_79cbed0c6707536e`: "Any business, like any household, has items that are wasted. Unlike a household, a business does keep track of all items that are unsellable. Depending on the reason for the item being unsellable they are accounted for differently. Items that can be returned to the manufacturer are done so, and the…
- rerank top-1 `r_543af255995d8797`: Wal-mart pays their employees so little, many of the workers need to be on foodstamps, in fact, the store has programs helping their workers apply for foodstamps. Are you ok with that? The only reason wal-mart gets away with paying them so little is because the government is basically propping them …
- category: keyword distractor 
- why: the gold doc explains how businesses account for unsellable items (returns to the manufacturer, write-offs), which answers the query although it never names Walmart; the reranker's top doc is about Walmart's low wages and food stamps, unrelated to inventory; the reranker is drawn by the shared words "Wal-mart" and "food"

### q_0330d32636d2c079 [EXAMPLE: RRF FAILS]
- transcript: "What are the reasons someone might choose to sell call options?"
- gold rank (top-20): enc_a 8 | rerank 17 | rrf 11
- gold `r_9c49397c1e4fd36d`: You appear to be thinking of option writers as if they were individuals with small, nondiversified, holdings and a particular view on what the underlying is going to do. This is not the best way to think about them. Option writers are typically large institutions with large portfolios and that provi…
- rerank top-1 `r_8f6062326c011486`: I would make a change to the answer from olchauvin: If you buy a call, that's because you expect that the value of call options will go up. So if you still think that options prices will go up, then a sell-off in the stock may be a good point to buy more calls for cheaper. It would be your call at t…
- category: wording mismatch
- why: the gold doc explains why option writers (i.e. sellers) are usually large institutions with diversified portfolios, which answers the query in jargon without the word "sell"; the reranker's top doc is about buying calls, the opposite side, and does not answer the question; the reranker is drawn by shared words ("call", "options", "sell-off") and does not link "sell" to "writers"

### q_69063f07ffde4b76
- transcript: "How can one organize their finances and assign a number to each record type?"
- gold rank (top-20): enc_a 6 | rerank 11 | rrf 9
- gold `r_5c05f92467a2b0d9`: "What you are describing is a Chart of Accounts. It's a structure used by accountants to categorise accounts into sub-categories below the standard Asset/Liability/Income/Expense structure. The actual categories used will vary widely between different people and different companies. Every person and…
- rerank top-1 `r_8af2821da6b0514a`: "The short answer is ""it depends"", mainly on the type of record and how old it is. Most retained records should be organized by year first, then by type. Have a look at this: http://www.bankrate.com/finance/personal-finance/how-long-to-keep-financial-records.aspx Typically, you should do the follo…
- category: wording mismatch
- why: the gold doc names what the user describes, a chart of accounts with numbered categories, which answers the query in accounting terms without "organize" or "record type"; the reranker's top doc is about how long to keep financial records, using "record" in the sense of documents; the reranker matches the shared words ("record", "type", "organized") rather than the meaning

### q_9c3b1086df278d77
- transcript: "How do government bonds yields function?"
- gold rank (top-20): enc_a 2 | rerank 12 | rrf 4
- gold `r_7466472f423a5098`: Why does the rising price of a bond pushes it's yield down? The bond price and its yield are linked; if one goes up, the other must go down. This is because the cash flows from the bond are fixed, predetermined. The market price of the bond fluctuates. Now what if people are suddenly willing to pay …
- rerank top-1 `r_f367c59aafa80569`: Yield is the term used to describe how much income the bond will generate if the bond was purchased at a particular moment in time. If I pay $100 for a one year, $100 par value bond that pays 5% interest then the bond yields 5% since I will receive $5 from a $100 investment if I held the bond to mat…
- category: plausible alternative
- why: the gold doc explains why bond prices and yields move inversely, which answers the query; the reranker's top doc defines yield with a worked example ($100 bond, 5% interest), an equally direct answer to how yields work; neither mentions government bonds, and only one is labelled

### q_86548cb995ca1db0
- transcript: "Did my sales representative harm my credit? What can I do about it?"
- gold rank (top-20): enc_a 4 | rerank 16 | rrf 9
- gold `r_1491a1c5f0d4d102`: You can sue them for damages. It would be hard to convince the court that the drop in the credit score was because of that loan, but not unthinkable. Especially if you sue through the small-claims court, where the burden of proof is slightly less formal, you have a chance to win and have them pay th…
- rerank top-1 `r_a612571c5a0be49b`: Nothing will happen. It will not affect your credit score. You are not in trouble. :) Assuming that you didn't already agree to a purchase contract, you are not obligated to purchase simply because you had a pre-approval credit check done. However, even if you did, since they aren't shipping yet, yo…
- category: vague query
- why: the gold doc advises suing in small-claims court over a loan that lowered the credit score, a context the query never mentions; the reranker's top doc says a pre-approval credit check does not affect the score, a reasonable answer to the query as spoken; without the missing context, both readings fit

## rerank: rescued (enc_a miss@10 -> hit)

### q_9cd791a970ab648f
- transcript: "Timeline for fund availability when depositing credit card payments."
- gold rank (top-20): enc_a 14 | rerank 7 | rrf 12
- gold `r_d545ea482fbce248`: For those who don't know, credit card checks are blank checks that your credit card company sends you. When you fill them out and spend them, you are taking a cash advance on your credit card account. You should be aware that taking a cash advance on your credit card normally has extra fees and fina…
- rerank top-1 `r_a9f492a705972ea7`: This is normal for credit cards. As long as you make the credit card company's cutoff time, they will make the funds available on your credit card rather than make you wait for them to actually get the funds from your bank. The amount of time this takes actually can vary significantly from bank to b…
- category: 
- why: 

### q_0c244d4030fd08ec
- transcript: "What are the methods and principles for valuing financial options?"
- gold rank (top-20): enc_a 11 | rerank 10 | rrf 12
- gold `r_939ac4e1656a98cf`: "Below I will try to explain two most common Binomial Option Pricing Models (BOPM) used. First of all, BOPM splits time to expiry into N equal sub-periods and assumes that in each period the underlying security price may rise or fall by a known proportion, so the value of an option in any sub-period…
- rerank top-1 `r_d295e9f0aff235a2`: Aside of the other (mostly valid) answers, share price is the most common method of valuating the company. Here is a bogus example that will help you understand the general point: Now, suppose that Company A wants to borrow $20 Million from a bank... Not a chance. Company B? Not a problem. Same situ…
- category: 
- why: 

### q_d76c858510d1e999
- transcript: "What is the income tax on my online dropshipping business in India?"
- gold rank (top-20): enc_a 11 | rerank 6 | rrf 10
- gold `r_f4d07c4f69080c38`: Please consult a tax advisor. You may be voilating the FEMA [Foreign Exchange Management Act] and can land into trouble. Further what you are doing can land up into various other acts as illegal including AML. Further if there is income generated by Indian citizen in India, he is still liable to pay…
- rerank top-1 `r_a4f5f4ab7a78b2d9`: I am from India. I visited US 6-8 times on business VISA and then started 2 Member LLC. Myself and My wife as LLC Members. We provide Online Training to american students from India. Also Got EIN number. Never employed any one. Do i need to pay taxes? Students from USA pays online by Paypal and i am…
- category: 
- why: 

### q_d40345916def841c [EXAMPLE: RRF DROPS]
- transcript: "What is the best way to use a credit card to improve credit score?"
- gold rank (top-20): enc_a 16 | rerank 8 | rrf 12
- gold `r_b6c405319f50aa8b`: "First I would like to say, do not pay credit card companies in an attempt to improve your credit rating. In my opinion it's not worth the cash and not fair for the consumer. There are many great resources online that give advice on how to improve your credit score. You can even simulate what would …
- rerank top-1 `r_a28461eafb69f362`: The best way to use your new credit card to establish credit history is to use it for small-medium purchases and pay it off in full each month. There is no reward for using it more than once a month. If you are getting some sort of rewards for using the credit card to pay your health insurance (air …
- category: matches a key phrase
- why: the gold doc warns against paying for credit repair and points to online resources, only partly answering the query, but repeats its phrase "improve your credit score"; enc_a ranks it 16th, possibly misled by the negative opening; the reranker matches the phrase and lifts it to 8th, while its top doc (pay off small purchases in full each month) answers the query more directly

### q_2e2cafa7d98b7fd1
- transcript: "Is it possible to invest in the housing market through the stock exchange?"
- gold rank (top-20): enc_a 18 | rerank 10 | rrf 17
- gold `r_8ee91772645a5677`: You could look into an index fund or ETF that invests primarily in Real Estate Investment Trusts (REIT's). An REIT is any corporation, trust or association that acts as an investment agent specializing in real estate and real estate mortgages Many investment firms offer an index fund or ETF like thi…
- rerank top-1 `r_d47b359376e0fbfd`: It might be easiest to think of stock exchanges like brokers. If you buy a home, and your broker goes bankrupt, you still own your home, but you could not sell it without the aid of another broker. Same with stocks, you own the stocks you buy, but you would be unable to either purchase new stocks or…
- category: links different wording
- why: the gold doc answers directly (buy an ETF of REITs, i.e. real estate traded on exchanges) but uses REIT/ETF terms instead of "housing market" or "stock exchange", so enc_a ranks it 18th; the reranker partly links housing to real estate and lifts it only to 10th, while its top doc is a broker analogy that shares "home" and "stock exchanges" but does not answer

### q_127367f6b97a8759 [EXAMPLE: RERANK RESCUES]
- transcript: "Is it advantageous to convert non investment real estate into rental property if I need to make significant repairs, USA, Missouri."
- gold rank (top-20): enc_a 19 | rerank 2 | rrf 4
- gold `r_7a751a1062c4575a`: "I don't have a direct answer for you, but here are some other things you might consider to help you decide on a course of action in addition to Joe's note about consulting a CPA... Get a couple contractors out to look the place over and give you some quotes on the work needed, most will do so for f…
- rerank top-1 `r_7c2e199ae1c9a288`: "The obvious advantage is turning your biggest liability into an income-generating asset. The downside are: (1), you have to find tenants (postings, time to show the place, credit/background check, and etc) (2), you have to deal with tenants (collection of rent, repairs of things that broke by itsel…
- category: matches a key condition in a long query
- why: the gold doc gives practical steps for the repair condition (get contractor quotes, consult a CPA) after a hedging opening; enc_a compresses the long multi-part query into one vector and ranks it 19th; the reranker reads query and doc together and links "significant repairs" to contractor quotes for the work needed

### q_60eaee4e6226cc0f
- transcript: "What are the implications of being classified as a day trader in Australia?"
- gold rank (top-20): enc_a 13 | rerank 5 | rrf 7
- gold `r_11cea4467061c03b`: In Australia the ATO can determine if you are considered a shareholder or a share trader. The ATO defines a shareholder as: A shareholder is a person who holds shares for the purpose of earning income from dividends and similar receipts. Whilst they define a share trader as: A share trader is a pers…
- rerank top-1 `r_2808bc248a67ba7b`: You need to contact the trading company and ask them what's going on. If it's simply a matter of needing to add more cash because you are now classified as a day trader, then call them, ask them what you need to do to not be considered a day trader, and do that. It would likely consist of not tradin…
- category: 
- why: 

### q_339b9b2f4d59a6f8
- transcript: "How is income from stocks, bonds, and real estate rent taxed for a U K limited company?"
- gold rank (top-20): enc_a 12 | rerank 1 | rrf 2
- gold `r_de9ef83e6cfd0887`: For stocks, bonds, ETF funds and so on - Taxed only on realised gain and losses are deductible from the gain and not from company's income. Corporate tax is calculated only after all expenses have been deducted. Not the other way around. Real estate expenses can be deducted because of repairs and ma…
- rerank top-1 `r_de9ef83e6cfd0887` (gold): For stocks, bonds, ETF funds and so on - Taxed only on realised gain and losses are deductible from the gain and not from company's income. Corporate tax is calculated only after all expenses have been deducted. Not the other way around. Real estate expenses can be deducted because of repairs and ma…
- category: 
- why: 

### q_3128e3949170573d
- transcript: "What are the benefits of foreign currency for a country?"
- gold rank (top-20): enc_a 14 | rerank 4 | rrf 6
- gold `r_573659e9d95a56ea`: Let me ask you another question: if that person stayed at home and made a widget instead, would exporting that widget benefit his home country? There is no difference, economically, between the two situations. A foreign worker sending home remittances is no different from a local manufacturer export…
- rerank top-1 `r_fcb6131c9f4e5936`: "US currency, today, can be used for useful things like selling a car, but there's nothing stopping you for trading it for something else. On edit; I've been thinking about this, and I think that the problem is that currency exists as a. edium to pay taxes. The usefulness of it for non-governmental …
- category: 
- why: 

### q_8ef57dbb7e83f8d2
- transcript: "How can I resolve ISA cash shares transfer delays?"
- gold rank (top-20): enc_a 12 | rerank 4 | rrf 7
- gold `r_254de1cdb000df24`: "One possibility you may consider is to keep all of your funds in the stocks and shares ISA while investing that proportion you wish to keep in cash into a tradeable ""Money Market"" ETF. A Money Market ETF will give you rates comparable to interest rates on cash and at the same time it will give yo…
- rerank top-1 `r_b06384f4133cb013`: Your existing shares in their existing ISA(s) do not in any way impact on your future ISA allowances. The only thing that uses up your ISA allowance is you paying new cash into an ISA account. So you can leave your existing shares in their existing ISA(s) and simply open new ISA(s) for future contri…
- category: 
- why: 

### q_6131855e6da3567e [EXAMPLE: RRF RESCUES]
- transcript: "What key metrics should I consider when evaluating investment returns?"
- gold rank (top-20): enc_a 14 | rerank 1 | rrf 2
- gold `r_422e9117ec6f0961`: "(Value of shares+Dividends received)/(Initial investment) would be the typical formula though this is more of a percentage where 1 would indicate that you broke even, assuming no inflation to be factored. No, you don't have to estimate the share price based on revenues as I would question how well …
- rerank top-1 `r_422e9117ec6f0961` (gold): "(Value of shares+Dividends received)/(Initial investment) would be the typical formula though this is more of a percentage where 1 would indicate that you broke even, assuming no inflation to be factored. No, you don't have to estimate the share price based on revenues as I would question how well …
- category: links different wording
- why: the gold doc answers with a formula for return ((value of shares + dividends) / initial investment) rather than naming "metrics"; enc_a ranks it 14th; the reranker recognises the formula as a measure of investment return and ranks it first

### q_85da6e74da0df100 [EXAMPLE: RERANK RESCUES]
- transcript: "Retirement and asset allocation for thirty thousand dollars, thirty years old, single."
- gold rank (top-20): enc_a 19 | rerank 3 | rrf 6
- gold `r_9819816b4dc3ab0b`: I would definitely recommend putting some of this in an IRA. You can't put all $30K in an IRA immediately though, as the contribution limit is $5500/year for 2014, but until April 15 you can still contribute $5500 for 2013 as well. At your income level I would absolutely recommend a Roth IRA, as you…
- rerank top-1 `r_1c6fb51ebc9f4b11`: "I would start with long term data. It would show how 40 years worth of stock investing puts the investor so far ahead of the ""safe"" investor that they can afford to lose half and still be ahead. But - then I would explain about asset allocation, and how the soon to be retired person had better be…
- category: links different wording
- why: the gold doc recommends a (Roth) IRA for the $30K, which answers the retirement question without the words "retirement" or "asset allocation"; enc_a ranks it 19th because the query's key terms do not appear; the reranker links "retirement" to "IRA"

### q_2987aa361da29f11
- transcript: "How will the net assets of a bankrupt company be distributed among common shareholders?"
- gold rank (top-20): enc_a 11 | rerank 2 | rrf 4
- gold `r_7bfc769dd6e08926`: All investors of equal standing get the same proportion of the net assets on bankruptcy but not all shareholders are of equal standing. In general, once all liabilities are covered, bond holders are paid first as that type of investment is company debt, then preferred stock holders are paid out and …
- rerank top-1 `r_6fc411cf740665fd`: What drives the stock of bankrupt companies? The company's potential residual assets. When a company goes bankrupt it is required to sell its assets to pay off its debts. The funds raised from selling assets go to the following entities: The usual order of debt repayment, in terms of the lender, wil…
- category: 
- why: 

### q_01e4a6bd93b1c759
- transcript: "How should one allocate their investment portfolio, considering the possibility of a prolonged decline in the total stock market index?"
- gold rank (top-20): enc_a 12 | rerank 2 | rrf 3
- gold `r_ad63168268aa8520`: "Here are a few things that you could try. But note that they are all capable of failing. They will just reduce the chance of you personally having a lost decade. First a quibble: John Bogle advocates a total stock market index (something like Vanguard's VTSMX) instead of an S&P fund, as the latter …
- rerank top-1 `r_d075ea53507135f7`: "You're right, the asset allocation is one fundamental thing you want to get right in your portfolio. I agree 110%. If you really want to understand asset allocation, I suggest any and all of the following three books, all by the same author, William J. Bernstein. They are excellent – and yes I've r…
- category: 
- why: 

### q_670e17ac4bbc3f81
- transcript: "What are the consequences of overcontributing to a workplace or private pension plan?"
- gold rank (top-20): enc_a 11 | rerank 2 | rrf 3
- gold `r_5b3698c804eaeeff`: "Firstly (and this part is rather opinion-based) I would absolutely not think of making more pension contributions when you are currently totaling 6% of salary as ""over contributing"". There are some who argue that you should be putting a minimum of 20% away for retirement throughout your working l…
- rerank top-1 `r_9aa869bd4c361db6`: Massively over-promising pensions are a problem in numerous states. California has done this so catastrophically that they could easily be seen as a qualitatively different than others (not just a bit worse but so systemically damaging that it is a different type of problem than most states face).
- category: 
- why: 

### q_8706e2925ba6d565
- transcript: "How can I lend money at an interest rate tied to the prime rate?"
- gold rank (top-20): enc_a 13 | rerank 3 | rrf 7
- gold `r_15e1953945b06f0d`: Yes. In the US these are called certificates of deposit or savings accounts. Every run-of-the-mill bank offers them. You give the bank money and in return they pay you an interest rate that is some fraction of or (negative) offset from the returns they expect to make from your money. Since most inve…
- rerank top-1 `r_ec52da433e58464c`: The prime rate is the interest rate banks use amongst themselves to lend money to each other only. It is used as the basis (sometimes) for what interest rate banks charge you. The prime rate is based loosely on the Fed rate. There is a committee that meets regularly to set this and other industry in…
- category: 
- why: 

### q_4b55e9052526c457
- transcript: "What are the methods for generating income through the purchase or sale of options?"
- gold rank (top-20): enc_a 17 | rerank 6 | rrf 10
- gold `r_70e4688b93c0cf00`: "Not all call options that have value at expiration, exercise by purchasing the security (or attempting to, with funds in your account). On ETNs, they often (always?) settle in cash. As an example of an option I'm currently looking at, AVSPY, it settles in cash (please confirm by reading the documen…
- rerank top-1 `r_6bd761c5ef5d7b19`: "RoR for options you bought is fairly easy: (Current Value-Initial Cost)/Initial Cost gives you the actual return. If you want the rate of return, you need to annualize that number: You divide the return you got above by the number of days the investment was in place, and then multiply that number b…
- category: 
- why: 

### q_aa44e49ca5a259a3
- transcript: "What are the potential profits associated with selling a customer base?"
- gold rank (top-20): enc_a 20 | rerank 5 | rrf 10
- gold `r_be0733c88fd6afbf`: Yes, some companies sell personal data on their customers, but it almost always means a bad business due to reputation cost. The Financial Times even made a calculator to demonstrate how much personal information is worth: The sellers get pennies for the info, so that any decent business would earn …
- rerank top-1 `r_f59b32b32e552c1d`: Company X located outside a military base offer discounts to military as a form of marketing. They want to encourage a group of potential customers to use their store/service. In some cases they are competing with subsidized store on the base. In other cases their only competition is other stores ou…
- category: 
- why: 

### q_b84477f46ecd8337
- transcript: "How can a U.S. citizen purchase foreign stocks?"
- gold rank (top-20): enc_a 14 | rerank 1 | rrf 2
- gold `r_c38ad8a1591eab20`: For question #1, at least some US-based online brokers do permit direct purchases of stocks on foreign exchanges. Depending on your circumstances, this might be more cost effective than purchasing US-listed ADRs. One such broker is Interactive Brokers, which allows US citizens to directly purchase s…
- rerank top-1 `r_c38ad8a1591eab20` (gold): For question #1, at least some US-based online brokers do permit direct purchases of stocks on foreign exchanges. Depending on your circumstances, this might be more cost effective than purchasing US-listed ADRs. One such broker is Interactive Brokers, which allows US citizens to directly purchase s…
- category: finds the specific question among similar docs
- why: the gold doc names brokers that let US citizens buy directly on foreign exchanges, matching the query closely; enc_a ranks it 14th among many similar docs on US investors and foreign stocks (e.g. tax implications); the reranker reads the specific ask ("how can … purchase") and ranks it first

### q_3dd947bc526a7484
- transcript: "How can one start a large business with a limited income?"
- gold rank (top-20): enc_a 12 | rerank 3 | rrf 5
- gold `r_f008c63b6a725cae`: "There are three (or four) ways that a company can grow: (Crowdfunding is a relatively new (in mainstream businesses) alternative financing method where people will finance a company with the expectation that they will benefit from the product or service that they provide.) Obviously a startup has n…
- rerank top-1 `r_184b7d5c53a2bd48`: "I think you should really start a limited company for this. It'll be a lot simpler to spread the income over multiple years if your business and you have completely separate identities. You should also consult an accountant, if only once to understand the basics of how to approach this. Having a li…
- category: 
- why: 

### q_097e324123569e77
- transcript: "Is it possible to purchase stock options at the bid price or below?"
- gold rank (top-20): enc_a 12 | rerank 2 | rrf 3
- gold `r_6ed1e84d18a2e083`: I understand the question, I think. The tough thing is that trades over the next brief time are random, or appear so. So, just as when a stock is $10.00 bid / $10.05 ask, if you place an order below the ask, a tick down in price may get you a fill, or if the next trades are flat to higher, you might…
- rerank top-1 `r_9d1746681627cdf7`: At the higher level - yes. The value of an OTM (out of the money) option is pure time value. It's certainly possible that when the stock price gets close to that strike, the value of that option may very well offer you a chance to sell at a profit. Look at any OTM strike bid/ask and see if you can f…
- category: 
- why: 

## rrf: broken (enc_a hit@10 -> miss)

### q_890a6df9ce937b08
- transcript: "How can I determine the exact time a SWIFT is issued by a bank?"
- gold rank (top-20): enc_a 10 | rerank 12 | rrf 11
- gold `r_c4b0886ff3312f06`: I think technically the MIR includes the date of issuance but not the time, see the references here. What you have there looks like a timestamp followed by the MIR. If you look at this example from IBM they also show the input time as a separate field.
- rerank top-1 `r_c1dc72a1adb0e960`: No. You can initiate SWIFT payments from Bank A, whenever Bank A is open for business. The transaction takes around 2-5 days for it to complete depending on the currency pair and countries involved. Once you initiate the payment, the Bank A sends it to SWIFT Network which in turn send it to Bank B. …
- category: wording mismatch
- why: the gold doc answers the question in SWIFT message terms (MIR has the date, input time is a separate field) without the words "issued"/"exact time"; the reranker prefers a doc on SWIFT transfer timing (2–5 days) that shares surface words but answers a different question

### q_cbb4c2670652d081
- transcript: "I am thirty years old and have saved thirty thousand dollars. What should I do with it?"
- gold rank (top-20): enc_a 5 | rerank 19 | rrf 11
- gold `r_cf8cc96996d99cab`: "First, two preliminaries, to address good points people made in comments. As AbraCadaver noted, before you move your $30k to something that might lose money, make sure you have enough cash to serve as an emergency fund in case you lose your income. Especially remember that big stock market crashes …
- rerank top-1 `r_59206e0770748944`: "First of all, kudos for thinking about budgeting at 21 years old. So many people don't plan with their money, and years later wonder where it all went. You are doing a lot of things right with your budget. You've got saving goals, namely your next car and a down payment on a house. You are saving a…
- category: same-topic disctractor
- why: the gold doc answers what to do with the $30k (keep an emergency fund first) but opens with replies to comments; the reranker's top doc is generic budgeting advice for a 21-year-old and never says what to do with the money; the reranker matches surface features (young saver, savings goals) and cannot link "thirty thousand dollars" to "$30k"

### q_0330d32636d2c079
- transcript: "What are the reasons someone might choose to sell call options?"
- gold rank (top-20): enc_a 8 | rerank 17 | rrf 11
- gold `r_9c49397c1e4fd36d`: You appear to be thinking of option writers as if they were individuals with small, nondiversified, holdings and a particular view on what the underlying is going to do. This is not the best way to think about them. Option writers are typically large institutions with large portfolios and that provi…
- rerank top-1 `r_8f6062326c011486`: I would make a change to the answer from olchauvin: If you buy a call, that's because you expect that the value of call options will go up. So if you still think that options prices will go up, then a sell-off in the stock may be a good point to buy more calls for cheaper. It would be your call at t…
- category: wording mismatch
- why: the gold doc explains why option writers (i.e. sellers) are usually large institutions with diversified portfolios, which answers the query in jargon without the word "sell"; the reranker's top doc is about buying calls, the opposite side, and does not answer the question; the reranker is drawn by shared words ("call", "options", "sell-off") and does not link "sell" to "writers"

## rrf: rescued (enc_a miss@10 -> hit)

### q_d76c858510d1e999
- transcript: "What is the income tax on my online dropshipping business in India?"
- gold rank (top-20): enc_a 11 | rerank 6 | rrf 10
- gold `r_f4d07c4f69080c38`: Please consult a tax advisor. You may be voilating the FEMA [Foreign Exchange Management Act] and can land into trouble. Further what you are doing can land up into various other acts as illegal including AML. Further if there is income generated by Indian citizen in India, he is still liable to pay…
- rrf top-1 `r_36efeba4cfeb7ad1`: This is taxable in India. You need to declare the income and pay taxes accordingly
- category: 
- why: 

### q_127367f6b97a8759
- transcript: "Is it advantageous to convert non investment real estate into rental property if I need to make significant repairs, USA, Missouri."
- gold rank (top-20): enc_a 19 | rerank 2 | rrf 4
- gold `r_7a751a1062c4575a`: "I don't have a direct answer for you, but here are some other things you might consider to help you decide on a course of action in addition to Joe's note about consulting a CPA... Get a couple contractors out to look the place over and give you some quotes on the work needed, most will do so for f…
- rrf top-1 `r_7c2e199ae1c9a288`: "The obvious advantage is turning your biggest liability into an income-generating asset. The downside are: (1), you have to find tenants (postings, time to show the place, credit/background check, and etc) (2), you have to deal with tenants (collection of rent, repairs of things that broke by itsel…
- category: 
- why: 

### q_60eaee4e6226cc0f
- transcript: "What are the implications of being classified as a day trader in Australia?"
- gold rank (top-20): enc_a 13 | rerank 5 | rrf 7
- gold `r_11cea4467061c03b`: In Australia the ATO can determine if you are considered a shareholder or a share trader. The ATO defines a shareholder as: A shareholder is a person who holds shares for the purpose of earning income from dividends and similar receipts. Whilst they define a share trader as: A share trader is a pers…
- rrf top-1 `r_2808bc248a67ba7b`: You need to contact the trading company and ask them what's going on. If it's simply a matter of needing to add more cash because you are now classified as a day trader, then call them, ask them what you need to do to not be considered a day trader, and do that. It would likely consist of not tradin…
- category: 
- why: 

### q_339b9b2f4d59a6f8
- transcript: "How is income from stocks, bonds, and real estate rent taxed for a U K limited company?"
- gold rank (top-20): enc_a 12 | rerank 1 | rrf 2
- gold `r_de9ef83e6cfd0887`: For stocks, bonds, ETF funds and so on - Taxed only on realised gain and losses are deductible from the gain and not from company's income. Corporate tax is calculated only after all expenses have been deducted. Not the other way around. Real estate expenses can be deducted because of repairs and ma…
- rrf top-1 `r_9bce79b98d116691`: Income and Capital are taxed separately in the uk. You probably can't get dividends paid gross even in ISA's you pay the basic rate of tax on dividends only higher rate tax payers get tax benefit from dividends. What you could do is invest in splits (Spilt capital investment trusts ) in the share cl…
- category: 
- why: 

### q_3128e3949170573d
- transcript: "What are the benefits of foreign currency for a country?"
- gold rank (top-20): enc_a 14 | rerank 4 | rrf 6
- gold `r_573659e9d95a56ea`: Let me ask you another question: if that person stayed at home and made a widget instead, would exporting that widget benefit his home country? There is no difference, economically, between the two situations. A foreign worker sending home remittances is no different from a local manufacturer export…
- rrf top-1 `r_0cb7b506ada679a6`: Short answer: NO, there is no financial benefits for you to expect in a local currency even if some might give tiny discounts on local sales. Local currencies are attractive for small business or communities, they are perfectly legal and starting to be popular in a lot of places. Local currencies en…
- category: 
- why: 

### q_8ef57dbb7e83f8d2
- transcript: "How can I resolve ISA cash shares transfer delays?"
- gold rank (top-20): enc_a 12 | rerank 4 | rrf 7
- gold `r_254de1cdb000df24`: "One possibility you may consider is to keep all of your funds in the stocks and shares ISA while investing that proportion you wish to keep in cash into a tradeable ""Money Market"" ETF. A Money Market ETF will give you rates comparable to interest rates on cash and at the same time it will give yo…
- rrf top-1 `r_39f1517889e21966`: I believe your last requirement is the main problem. AIUI the law requires that ISA providers allow withdrawals. They can require a notice period and they can penalise you (e.g. via lost interest) for withdrawing but they cannot prevent you accessing your money for an extended period.
- category: 
- why: 

### q_6131855e6da3567e
- transcript: "What key metrics should I consider when evaluating investment returns?"
- gold rank (top-20): enc_a 14 | rerank 1 | rrf 2
- gold `r_422e9117ec6f0961`: "(Value of shares+Dividends received)/(Initial investment) would be the typical formula though this is more of a percentage where 1 would indicate that you broke even, assuming no inflation to be factored. No, you don't have to estimate the share price based on revenues as I would question how well …
- rrf top-1 `r_3a2fa0d033caac7a`: "Is evaluating stocks just a loss of time if the stock is traded very much? Not at all! Making sound investment decisions based on fundamental analysis of companies will help you to do decide whether a given company is right for you and your risk appetite. Investing is not a zero-sum game, and you c…
- category: 
- why: 

### q_85da6e74da0df100
- transcript: "Retirement and asset allocation for thirty thousand dollars, thirty years old, single."
- gold rank (top-20): enc_a 19 | rerank 3 | rrf 6
- gold `r_9819816b4dc3ab0b`: I would definitely recommend putting some of this in an IRA. You can't put all $30K in an IRA immediately though, as the contribution limit is $5500/year for 2014, but until April 15 you can still contribute $5500 for 2013 as well. At your income level I would absolutely recommend a Roth IRA, as you…
- rrf top-1 `r_cb2880a0ef22d53f`: I would focus first on maxing out your RRSPs (or 401k) each year, and once you've done that, try to put another 10% of your income away into unregistered long term growth savings. Let's say you're 30 and you've been doing that since you graduated 7 years ago, and maybe you averaged 8% p.a. return an…
- category: 
- why: 

### q_2987aa361da29f11
- transcript: "How will the net assets of a bankrupt company be distributed among common shareholders?"
- gold rank (top-20): enc_a 11 | rerank 2 | rrf 4
- gold `r_7bfc769dd6e08926`: All investors of equal standing get the same proportion of the net assets on bankruptcy but not all shareholders are of equal standing. In general, once all liabilities are covered, bond holders are paid first as that type of investment is company debt, then preferred stock holders are paid out and …
- rrf top-1 `r_6fc411cf740665fd`: What drives the stock of bankrupt companies? The company's potential residual assets. When a company goes bankrupt it is required to sell its assets to pay off its debts. The funds raised from selling assets go to the following entities: The usual order of debt repayment, in terms of the lender, wil…
- category: 
- why: 

### q_01e4a6bd93b1c759
- transcript: "How should one allocate their investment portfolio, considering the possibility of a prolonged decline in the total stock market index?"
- gold rank (top-20): enc_a 12 | rerank 2 | rrf 3
- gold `r_ad63168268aa8520`: "Here are a few things that you could try. But note that they are all capable of failing. They will just reduce the chance of you personally having a lost decade. First a quibble: John Bogle advocates a total stock market index (something like Vanguard's VTSMX) instead of an S&P fund, as the latter …
- rrf top-1 `r_d075ea53507135f7`: "You're right, the asset allocation is one fundamental thing you want to get right in your portfolio. I agree 110%. If you really want to understand asset allocation, I suggest any and all of the following three books, all by the same author, William J. Bernstein. They are excellent – and yes I've r…
- category: 
- why: 

### q_670e17ac4bbc3f81
- transcript: "What are the consequences of overcontributing to a workplace or private pension plan?"
- gold rank (top-20): enc_a 11 | rerank 2 | rrf 3
- gold `r_5b3698c804eaeeff`: "Firstly (and this part is rather opinion-based) I would absolutely not think of making more pension contributions when you are currently totaling 6% of salary as ""over contributing"". There are some who argue that you should be putting a minimum of 20% away for retirement throughout your working l…
- rrf top-1 `r_9aa869bd4c361db6`: Massively over-promising pensions are a problem in numerous states. California has done this so catastrophically that they could easily be seen as a qualitatively different than others (not just a bit worse but so systemically damaging that it is a different type of problem than most states face).
- category: 
- why: 

### q_8706e2925ba6d565
- transcript: "How can I lend money at an interest rate tied to the prime rate?"
- gold rank (top-20): enc_a 13 | rerank 3 | rrf 7
- gold `r_15e1953945b06f0d`: Yes. In the US these are called certificates of deposit or savings accounts. Every run-of-the-mill bank offers them. You give the bank money and in return they pay you an interest rate that is some fraction of or (negative) offset from the returns they expect to make from your money. Since most inve…
- rrf top-1 `r_d2cc2318b648d78a`: No. The WSJ prime rate is 4.25%, even the Fed prime rate is 1.75%, way above the 1.20% you'll be making from your savings account. If you are high worth individual with great credit history, the bank might give you a personal loan at 4.25%. They won't care what you do with it as long as they get the…
- category: 
- why: 

### q_4b55e9052526c457
- transcript: "What are the methods for generating income through the purchase or sale of options?"
- gold rank (top-20): enc_a 17 | rerank 6 | rrf 10
- gold `r_70e4688b93c0cf00`: "Not all call options that have value at expiration, exercise by purchasing the security (or attempting to, with funds in your account). On ETNs, they often (always?) settle in cash. As an example of an option I'm currently looking at, AVSPY, it settles in cash (please confirm by reading the documen…
- rrf top-1 `r_da4990cbd605a0f8`: So, child, your goal is to make money? This is usually achieved by selling goods (say, lemonade) at a price that exceeds their cost (say, sugar, water and, well, lemons). Options, at first, are very much same in that you can buy the right to engage in a specific future trade. You make money in this …
- category: 
- why: 

### q_aa44e49ca5a259a3
- transcript: "What are the potential profits associated with selling a customer base?"
- gold rank (top-20): enc_a 20 | rerank 5 | rrf 10
- gold `r_be0733c88fd6afbf`: Yes, some companies sell personal data on their customers, but it almost always means a bad business due to reputation cost. The Financial Times even made a calculator to demonstrate how much personal information is worth: The sellers get pennies for the info, so that any decent business would earn …
- rrf top-1 `r_e5c52c8c94f679cc`: Wow. Okay. First do you mean that you profited by 30k or that you have 30k in revenue? Second why are you selling it? Do you not want it? Can you not grow it? Why or why not? I feel like you’re going to need to flesh out your business a little more to get a better answer.
- category: 
- why: 

### q_b84477f46ecd8337
- transcript: "How can a U.S. citizen purchase foreign stocks?"
- gold rank (top-20): enc_a 14 | rerank 1 | rrf 2
- gold `r_c38ad8a1591eab20`: For question #1, at least some US-based online brokers do permit direct purchases of stocks on foreign exchanges. Depending on your circumstances, this might be more cost effective than purchasing US-listed ADRs. One such broker is Interactive Brokers, which allows US citizens to directly purchase s…
- rrf top-1 `r_800022095f385cc7`: If you are a US citizen, you need to very carefully research the US tax implications of investing in foreign stocks before you do so. The US tax rules have been set up in general to make this very unattractive.
- category: 
- why: 

### q_3dd947bc526a7484
- transcript: "How can one start a large business with a limited income?"
- gold rank (top-20): enc_a 12 | rerank 3 | rrf 5
- gold `r_f008c63b6a725cae`: "There are three (or four) ways that a company can grow: (Crowdfunding is a relatively new (in mainstream businesses) alternative financing method where people will finance a company with the expectation that they will benefit from the product or service that they provide.) Obviously a startup has n…
- rrf top-1 `r_184b7d5c53a2bd48`: "I think you should really start a limited company for this. It'll be a lot simpler to spread the income over multiple years if your business and you have completely separate identities. You should also consult an accountant, if only once to understand the basics of how to approach this. Having a li…
- category: 
- why: 

### q_097e324123569e77
- transcript: "Is it possible to purchase stock options at the bid price or below?"
- gold rank (top-20): enc_a 12 | rerank 2 | rrf 3
- gold `r_6ed1e84d18a2e083`: I understand the question, I think. The tough thing is that trades over the next brief time are random, or appear so. So, just as when a stock is $10.00 bid / $10.05 ask, if you place an order below the ask, a tick down in price may get you a fill, or if the next trades are flat to higher, you might…
- rrf top-1 `r_9d1746681627cdf7`: At the higher level - yes. The value of an OTM (out of the money) option is pure time value. It's certainly possible that when the stock price gets close to that strike, the value of that option may very well offer you a chance to sell at a profit. Look at any OTM strike bid/ask and see if you can f…
- category: 
- why: 
