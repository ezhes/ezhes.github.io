---
title: "Benchmarking Popular Markdown Parsers on iOS"
date: 2018-02-18:T00:00:00+00:00
author: "Allison Husain"
tags: ["iOS", "performance"]
showFullContent: false
---

Reddit uses markdown for all of its posts and comments and so I needed a way to parse and render markdown not only well but *fast*. In the two years I've been working on this app of and on I've went through multiple differently libraries before I decided it'd be worthwhile to actually go and find the best one once and for all instead of just trying random ones, and so I decided to benchmark the top five I could find.

**TL;DR**: Use [CocoaMarkdown](https://github.com/HowdyHub/CocoaMarkdown). Skip to the end for a summary. 

## Test Methodology
I'm collecting two bits of data: 

1. How long it takes to complete 1000 full cycles (source text to display)
2. How much memory is uses max (and how much is leaked)

The library needs to be able to either take its source as HTML or markdown. I can do this because Reddit actually (for whatever reason) provides both HTML and markdown with every API request, wasting user's bandwidth everywhere.

![/blog/images/markdown_ios_benchmarks/markdown_html_reddit.png](/blog/images/markdown_ios_benchmarks/markdown_html_reddit.png)

[This is the markdown/HTML sample I'm using. It's long and has lots of weird formatting. It even makes Chrome stutter when rendering.](https://www.reddit.com/r/reddit.com/comments/6ewgt/reddit_markdown_primer_or_how_do_you_do_all_that/c03nik6/) 

To test timing I used the following methods to time a code block:

*Objective C*:

```objectivec
-(void)totalRuntimeForMethod:(NSString*)method block:(void(^)(void))block;
{
    extern uint64_t dispatch_benchmark(size_t count, void (^block)(void));
    
    int iterations = 1000;
    uint64_t t = dispatch_benchmark(iterations, ^{
        @autoreleasepool {
            block();
        }
    });
    
    NSLog(@"Runtime for %i iterations (ms) %@: %f", iterations, method, t/1000000.0*iterations);
}
```

*Swift*:

```swift
func measure(_ title: String, block: (() -> ())) {
    let startTime = CFAbsoluteTimeGetCurrent()
    let iterations = 500
    
    for _ in 0..<(iterations) {
        block()
    }
    let timeElapsed = (CFAbsoluteTimeGetCurrent() - startTime) * 1000
    print("Runtime for \(iterations) iterations (ms) \(title): \(timeElapsed)")
}
```

All tests were performed on an iPhone X running iOS 11.2

## The Apple Way (`NSAttributedString`) -- HTML
iOS offers a nice looking native way to convert HTML (with very good CSS!) into `NSAttributedString`. 

```objectivec
[self totalRuntimeForMethod:@"NSAttributedStringHTML" block:^{
    NSDictionary *options = @{ NSDocumentTypeDocumentAttribute: NSHTMLTextDocumentType };
    NSAttributedString *attrStr = [[NSAttributedString alloc] initWithData:[html dataUsingEncoding:NSUTF8StringEncoding] options:options documentAttributes:NULL error:NULL];
    
    
    UITextView *textView = [[UITextView alloc]initWithFrame:self.view.frame textContainer:nil];
    [self.view addSubview:textView];
    textView.attributedText = attrStr;
    [textView layoutSubviews];
    
    [textView removeFromSuperview];
}];
```

It renders it very well but this comes at a cost.

`Runtime for 1000 iterations (ms) NSAttributedStringHTML: 88583.218000`

It's dreadfully slow. This is the method I used initially and it was most certainly not capable of just in time rendering, especially when trying to quickly scroll through reddit comments. 

In terms of memory usage though, the Apple way is very good. It leaked 10.7MB which is the highest leaked by any of the libraries. 

![/blog/images/markdown_ios_benchmarks/NSAttributedString_5000.png](/blog/images/markdown_ios_benchmarks/NSAttributedString_5000.png)

A note about reading these graphs: I left some time before starting the benchmark and then some after to let ARC and the OS try and free memory or whatever. The initial memory usage of this empty app is 17.3MB.

## [DTCoreText](https://github.com/Cocoanetics/DTCoreText) -- HTML
I implemented this in my app after a few months of suffering through `NSAttributedString`'s slowness. DTCoreText is both an HTML+CSS parser as well as a CoreText display engine, offering their own `DTAttributedTextView`. Unfortunately, the CSS parser here is quite a bit worse and doesn't support a lot of the same styling as Apple does. Despite this, it's a bit faster and I used it in my app for a year.

For DTCoreText I tested both their parser with `UITextView` and `DTAttributedTextView`.



*UITextView*:

```objectivec
[self totalRuntimeForMethod:@"DTCore" block:^{
    UITextView *textView = [[UITextView alloc]initWithFrame:self.view.frame textContainer:nil];
    DTHTMLAttributedStringBuilder *builder = [[DTHTMLAttributedStringBuilder alloc]initWithHTML:[html dataUsingEncoding:NSUTF8StringEncoding] options:@{DTUseiOS6Attributes : @true} documentAttributes:nil];
    NSAttributedString *generatedString = [builder generatedAttributedString];
    [self.view addSubview:textView];
    textView.attributedText = generatedString;
    [textView layoutSubviews];
    
    [textView removeFromSuperview];
}];
```

`Runtime for 1000 iterations (ms) DTCore UITextView: 72529.906000`

DTCoreText + UITextView finished a full 16 seconds sooner than `NSAttributedString`! It still did take 72.5 seconds but we'll ignore that for now.

Memory is great here. Lower max memory than Apple, and it only leaked 4.3MB!

![/blog/images/markdown_ios_benchmarks/DTCoreText_1000.png](/blog/images/markdown_ios_benchmarks/DTCoreText_1000.png)

*DTAttributedTextView*:

```objectivec
[self totalRuntimeForMethod:@"DTCore" block:^{
    DTAttributedTextView * textView = [[DTAttributedTextView alloc]initWithFrame:self.view.frame];
    DTHTMLAttributedStringBuilder *builder = [[DTHTMLAttributedStringBuilder alloc]initWithHTML:[html dataUsingEncoding:NSUTF8StringEncoding] options:@{DTUseiOS6Attributes : @true} documentAttributes:nil];
    NSAttributedString *generatedString = [builder generatedAttributedString];
    [self.view addSubview:textView];
    textView.attributedString = generatedString;
    [textView layoutSubviews];
    
    [textView removeFromSuperview];
}];
```

`Runtime for 1000 iterations (ms) DTCore w/ DTAttributedTextView: 101960.893000`

This was actually a bit of a surprise. I did not expect them to create their own text view system and ship it, knowing that it was actually SLOWER than the regular text view. 

Memory wasn't bad either but it was worse than using UITextView. 8.5MB leaked, 28.8MB max.

![/blog/images/markdown_ios_benchmarks/DTCore_DTAttributedTextView_1000.png](/blog/images/markdown_ios_benchmarks/DTCore_DTAttributedTextView_1000.png)

## [Down (Swift)](https://github.com/iwasrobbed/Down) -- Markdown
This is the first raw markdown parser I tested. I figured it'd be faster parsing markdown directly rather than HTML because markdown is much tighter and you don't have to parse CSS as well. 

```swift
measure("Down") {
    let down = Down.init(markdownString: markdown);
    let attributedString = try? down.toAttributedString();
    let textView = UITextView.init(frame: self.view.frame, textContainer: nil);
    self.view.addSubview(textView)
    textView.attributedText = attributedString!
    textView.layoutSubviews()
    textView.removeFromSuperview()
}
```

and it didn't finish 1000 rounds, it ran out of memory. Ouch. Rather than give Down a straight F, I dropped it down to 500 rounds

<iframe src='https://gfycat.com/ifr/ColossalHugeCicada' frameborder='0' scrolling='no' allowfullscreen data-hd=true></iframe>
(switch on HD, gfycat is weird)

`Runtime for 500 iterations (ms) Down: 23523.5600471497`. Assuming it scaled properly to 1000 rounds, this would be 47,047ms which is unequivocally better than DTCoreText and everything that came before it. But what's it doing with all this memory? 

The 500 round graph does shed some light on this

![/blog/images/markdown_ios_benchmarks/Down_500.png](/blog/images/markdown_ios_benchmarks/Down_500.png)

The graph spikes up to 1.12GB of usage but manages to drop all the way back down to 104MB. It's leaking quite a bit of memory but there's a much bigger problem going on too. I tossed it up into instruments and checked out the heap in the middle of one session (before it started releasing data):

![/blog/images/markdown_ios_benchmarks/Down_memory_alloc.png](/blog/images/markdown_ios_benchmarks/Down_memory_alloc.png)

It's like this for ages. From this snapshot we can determine quite a lot about how Down works. Firstly, it's not `cmark` (the markdown processor written in C) causing the memory issues as I initially suspected. I thought that there was something funky going own between C->Objective-C->Swift with ARC since that's a lot of ground to cover. Secondly, Down is parsing Markdown into HTML and then into AttributedText *for some reason*. This HTML parsing stage is somehow faster twice as fast as Apple but it obviously has issues.

Despite this, `Down` *is faster than all of the above* but they completely messed up the memory. I'm not sure how this will fare in a tableview where it will have down time to free memory vs. a continuous benchmark since I'm not going to bother implementing this since I will not use it.

## [Bypass](https://github.com/Uncodin/bypass-ios) -- Markdown

This one was a doozy to implement. It's five years old and doesn't support Auto Layout in any sense and the Cocoapod is a bit broken due to the fact that this library uses ObjC and ObjC++. I implemented this one in my app (by mistake, because initially I screwed up the benchmarks). The code though is quite painful to work with. There are some methods featuring a comment of "DON'T TOUCH UNLESS YOU FULLY UNDERSTAND WHAT'S GOING ON". 

Still though, Bypass is awesome. It support async rendering of text, which I didn't initially realize and caused my benchmarks for 1000 rounds to seem to only take 65ms. This 65ms however really was just the amount of time it took Bypass to dispatch the parse and draw and not actually the full amount of time required to render it. What initially drew me to Bypass was that fact that it uses its own parser and display view. It does not output to AttributedText at all, and it never drops to HTML or any intermediates and instead draws markdown directly using CoreText.

Note that this library also has some weird bugs with the way it attributes text at the end of a line. For whatever reason it refuses to apply formatting to the last character of any line. 

```objectivec
[self totalRuntimeForMethod:@"Bypass" block:^{
    BPMarkdownView *markdownView = [[BPMarkdownView alloc] initWithFrame:self.view.frame];
    [markdownView setMarkdown:markdownToRender];
    [[self view] addSubview:markdownView];
    //FORCE BYPASS TO RENDER THE VIEW
    [markdownView layoutSubviews];
    [markdownView removeFromSuperview];
}];
```

Note that I have to call `layoutSubviews`. Bypass doesn't bother doing anything until it's absolutely necessary unlike the other libraries. 

`Runtime for 1000 iterations (ms) Bypass: 21078.243000`

Half the time of `Down` but it doesn't destroy the memory!

![/blog/images/markdown_ios_benchmarks/Bypass_1000.png](/blog/images/markdown_ios_benchmarks/Bypass_1000.png)

3.7MB leaked. It also seems to have the same issue as `Down` where memory linearly increases with time instead of being perfectly flat throughout the benchmark. I believe that if I did a million or so rounds it may run out of memory but I don't have the time to bother testing that one. I don't consider this memory increase to be an issue since it only allocated 14MB on to the heap for 1000 rounds.

## [CocoaMarkdown](https://github.com/HowdyHub/CocoaMarkdown.git) -- Markdown
CocoaMarkdown renders to `NSAttributedString` which you are then supposed to put into a `UITextView`. It also uses `cmark` for parsing. It doesn't work though with Unicode though so if you need that keep this in mind.

```objectivec
[self totalRuntimeForMethod:@"CocoaMarkdown" block:^{
    CMDocument *d = [[CMDocument alloc]initWithData:[markdownToRender dataUsingEncoding:NSUTF8StringEncoding] options:CMDocumentOptionsSmart];
    CMTextAttributes *c = [[CMTextAttributes alloc]init];
    NSAttributedString *str = [[[CMAttributedStringRenderer alloc]initWithDocument:d attributes:c] render];
    
    UITextView *textView = [[UITextView alloc]initWithFrame:self.view.frame textContainer:nil];
    [self.view addSubview:textView];
    textView.attributedText = str;
    [textView layoutSubviews];
    
    [textView removeFromSuperview];
    
}];
```

`Runtime for 1000 iterations (ms) CocoaMarkdown: 8697.179000`

A full 12 seconds over `Bypass`. I was blown away by this. This is less than a eight milliseconds to parse and layout. There is no multithreaded trickery going on here. The attribution looks nice, the formatting class is extensible and easy to read, and it attributes most things correctly. None of these libraries, for whatever reason, support superscript but that isn't hard to add. I'll be making a pull request for Cocoamarkdown in the future to add this upstream.

To confirm my findings and validate my benchmarking system across both languages, I ran this same test in Swift:

```swift
measure("CocoaMarkdown") {
    [unowned self] in
    let doc = CMDocument.init(string: markdown, options: CMDocumentOptions.smart)
    let attributedString = CMAttributedStringRenderer.init(document: doc, attributes: CMTextAttributes.init()).render()
    let textView = UITextView.init(frame: self.view.frame, textContainer: nil);
    self.view.addSubview(textView)
    textView.attributedText = attributedString
    textView.layoutSubviews()
    textView.removeFromSuperview()
}
```

`Runtime for 1000 iterations (ms) CocoaMarkdown (swift): 8497.15805053711 ms`

Very close timings. I attribute the difference of 200ms to external CPU load and memory availability. Regardless, it confirms that the Swift and Objective-C tests are almost nearly identical.

In terms of memory usage, all is good (when using Objective-C). Leaking only 1.2MB on the Objective-C test and maxing out at 20.3 MB used, it also wins the memory usage metric.

![/blog/images/markdown_ios_benchmarks/Cocoamarkdown1000.png](/blog/images/markdown_ios_benchmarks/Cocoamarkdown1000.png)

For some reason, memory management goes a bit sideways on Swift. I have no idea *what* Swift is doing to manage to turn 20.3MB max into 262MB but somehow it did. I don't think this is `CocoaMarkdown`'s fault at all. Something weird is going on with the Swift runtime and the way it handles the memory of Objective-C functions. 

![/blog/images/markdown_ios_benchmarks/Cocoamarkdown_1000Swift.png](/blog/images/markdown_ios_benchmarks/Cocoamarkdown_1000Swift.png)

This appears to be the same issue which plagues `Down` however since `CocoaMarkdown` uses less memory per round it gets away with it a bit longer. I can do 4000 rounds successfully despite this issue, though with a terrifying memory graph: 

![/blog/images/markdown_ios_benchmarks/Cocoamarkdown4000swift.png](/blog/images/markdown_ios_benchmarks/Cocoamarkdown4000swift.png)

and again on Objective-C we see nothing of the sort and max out at a happy 28.7MB.

![/blog/images/markdown_ios_benchmarks/Cocoamarkdown4000objc.png](/blog/images/markdown_ios_benchmarks/Cocoamarkdown4000objc.png)


##Summary
If you need performance, CocoaMarkdown is unbeatable. It's fastest and most memory efficient (\* despite Swift being weird) and it works well. 

**Raw speed**:

|Library  | Time (ms)         | Speed difference over previous |
|------------- | -------------| ---- | 
| CocoaMarkdown (UITextView)  | 8497  | 2.48x|
| Bypass (BPMarkdownView)     | 21078 | 2.23x|
| Down (UITextView) \*expected| 47047 | 1.54x|
| DTCore (UITextView)         | 72529 | 1.22x|
|NSAttributedString (UITextView)| 88583| 1.15x|
|DTCore (DTAttributedTextView)| 101960| n/a, no worse result

<br>

Dramatic to say the least. Some fun stats: 

* CocoaMarkdown is ~12x faster than DTCore + DTAttributedTextView
* CocoaMarkdown is ~10.4x faster than NSAttributedStringHTML

<hr>

**Peak memory usage/max leaked (Swift results excluded due to bugginess)**:

|Library  | Peak usage (MB)         | Max leaked (MB) |
|------------- | -------------| ---- | 
| CocoaMarkdown (UITextView)  | 20.3  | 1.2|
| DTCore (UITextView)         | 23.9 | 4.3|
|DTCore (DTAttributedTextView)| 28.8| 8.5 |
| Bypass (BPMarkdownView)     | 31.3 | 3.7|
|NSAttributedString (UITextView)| 35.9| 10.7|

<hr>

Nothing really ground breaking here in terms of Objective-C however these results are amplified by about nine fold when used in Swift, for whatever reason. Unfortunately memory doesn't seem to be managed very well through Objective-C bridging. If you need perfect performance you'll still have to stay on Objective-C for now, until at least someone writes a 100% swift Markdown library from scratch.
