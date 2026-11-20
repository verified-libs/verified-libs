// operator new/delete on top of bench_heap.c's static arena, as bare-metal
// C++ firmware usually provides. Without these, libstdc++'s operator new
// pulls in abort() -> signal() -> newlib malloc -> sbrk. Out of memory traps
// in malloc (bench_heap.c), so these never return nullptr.
#include <cstddef>
#include <cstdlib>
#include <new>

extern "C" void *malloc(std::size_t);

void *operator new(std::size_t n) { return malloc(n); }
void *operator new[](std::size_t n) { return malloc(n); }
void *operator new(std::size_t n, std::align_val_t) { return malloc(n); } // arena is 64-byte aligned
void *operator new[](std::size_t n, std::align_val_t) { return malloc(n); }
void operator delete(void *) noexcept {}
void operator delete[](void *) noexcept {}
void operator delete(void *, std::size_t) noexcept {}
void operator delete[](void *, std::size_t) noexcept {}
void operator delete(void *, std::align_val_t) noexcept {}
void operator delete[](void *, std::align_val_t) noexcept {}
void operator delete(void *, std::size_t, std::align_val_t) noexcept {}
void operator delete[](void *, std::size_t, std::align_val_t) noexcept {}
