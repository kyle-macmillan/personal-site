---
title: "Intro to Data Compression with OCaml: Prefix-Free Codes"
date: '2025-11-06'
tags: ["compression"]
---

# Intro to Data Compression with OCaml: Prefix-Free Codes
{{< side-image
  src="/img/blog/caravaggio-musici.jpg"
  caption="Audio compression by hand, or The Musicians by Caravaggio (1595)."
>}}

There's no better time to learn about data compression than now, where "big
data" is now just "data." But even before large scale data analysis was
commonplace, limited bandwidth and storage capacity encouraged the design
of good compression algorithms. The enduring relevance and importance
of compression has convinced me to dig in and learn the basics of data
compression, as well as relevant information theoretic concepts.

To start, we'll introduce one of the fundamental building blocks of
compression: **prefix-free codes**. 

*N.B.*: All code examples will be written in OCaml. I've been looking for 
an excuse to learn the language and think it's a good fit for this 
application.   

# Source Coding






