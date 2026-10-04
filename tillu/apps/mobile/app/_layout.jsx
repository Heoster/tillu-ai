import {Stack} from'expo-router';import{StatusBar}from'expo-status-bar';
export default function Layout(){return <><StatusBar style="light"/><Stack screenOptions={{headerStyle:{backgroundColor:'#0d0c12'},headerTintColor:'#fff',contentStyle:{backgroundColor:'#0a0910'}}}/></>}
