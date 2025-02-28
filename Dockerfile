FROM python:3.12

RUN apt -qq update && \
    apt-get install -y wget cmake ninja-build make autoconf autogen automake libtool expect && \
    rm -rf /var/lib/apt/lists/*

RUN wget https://github.com/WebAssembly/wasi-sdk/releases/download/wasi-sdk-25/wasi-sdk-25.0-x86_64-linux.deb
RUN case `dpkg --print-architecture` in \
  amd64) dpkg -i wasi-sdk-*-x86_64-linux.deb ;; \
  arm64) dpkg -i wasi-sdk-*-arm64-linux.deb ;; \
  *) exit 1 ;; \
  esac && \
  rm wasi-sdk-*.deb

ENV PATH="/opt/wasi-sdk/bin:${PATH}"
ENV CC="/opt/wasi-sdk/bin/clang"
ENV CXX="/opt/wasi-sdk/bin/clang++"
ENV LD="/opt/wasi-sdk/bin/wasm-ld"
ENV AR="/opt/wasi-sdk/bin/llvm-ar"
ENV RANLIB="/opt/wasi-sdk/bin/llvm-ranlib"

RUN git clone https://github.com/spylang/spy.git
RUN mkdir -p /spy/scripts && cd spy && pip install -e . && make -C spy/libspy
VOLUME ["/spy/scripts"]
WORKDIR /spy
CMD ["bash"]
