// compile with: g++ -std=c++17 -Wall -Wextra matrix.cpp

template<typename T, int N>
struct Array {
    static_assert(N > 0, "Array<T, N>: N must be positive");
    T data[N];
};

template<typename T, int ROW, int COL>
struct Matrix {
    // BUG HERE: should be ROW * COL
    Array<T, ROW - COL> storage;
};

int main() {
    Matrix<int, 2, 3> m;
    (void)m; // silence unused variable warning
    return 0;
}
