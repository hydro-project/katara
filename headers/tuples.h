#include <tuple>
template <typename...T>
struct tup
{
	std::tuple<T...> contents;
};
template <typename...T>
using Tuple = tup<T...> *;

template <class...T>
Tuple<T...> newTuple() 
{
  
  return new tup<T...>();
}
template <class...T>
Tuple<T...> MakeTuple(T...args) 
{
  Tuple<T...> r = newTuple<T...>();
  r->contents = std::make_tuple(args...);
  return r;
}

//template <class...T, size_t I = 0 >
template <class...T, int I = 0 >
typename std::enable_if<(I < sizeof...(T)),
                   int>::type
 tupleGet(Tuple<T...> t, int i) 
{ 
		
		return std::get<I>(t->contents);

// switch (i) {
//         case 0: return get<i>(t->contents);
//         case 1: return get<1>(t->contents);
//     }
}


