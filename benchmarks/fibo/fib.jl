@inline function fib(n::Int64)::Int64
    return n <= 1 ? n : fib(n-2) + fib(n-1)
end

@time result = fib(Int64(40))
@time result = fib(Int64(40))
