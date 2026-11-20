/* Minimal stand-in for Mbed's platform/Span.h: CircularBuffer only names
 * mbed::Span in its Span overloads, which the adapter does not call. */
#pragma once
#include <stddef.h>
namespace mbed {
template<typename T> class Span {
public:
    Span(T *p, size_t n) : _p(p), _n(n) {}
    T *data() const { return _p; }
    size_t size() const { return _n; }
private:
    T *_p; size_t _n;
};
template<typename T> Span<T> make_Span(T *p, size_t n) { return Span<T>(p, n); }
}
