#include <vector>

template <typename T>
struct Array
{
  std::vector<T> contents;
};

template <typename T>
using Array = Array<T> *;


template <class T>
int arrayLength (Array<T> l) 
{
  return l->contents.size();
}

template <class T>
Array<T> newarray() 
{
  //return (Array<T>)malloc(sizeof(struct Array));
  return new Array<T>(100);
}

template <class T>
T arrayGet (Array<T> l, int i) 
{ 
  return l->contents[i];
}

template <class T>
void arraySet (Array<T> l, int i, int v) 
{ 
  l->contents[i] = v ;
}