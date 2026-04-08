/** @format */
// obj1
{
  a: 1
  b: {
    c: 2
  }
  d: {
    e: {
      f:3
    }
  }
}
// obj2

{
  b: {
    cc: 4
  }
  d: {
    ee: 33
    e: {
      f:4
      ff: 5
    }
  }
}

// merged obj

{
  a: 1
  b: {
    c: 2
    cc: 4
  }
  d: {
    ee:33
    e: {
      f:4
      ff: 5
    }
  }
}